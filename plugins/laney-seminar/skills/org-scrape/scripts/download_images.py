"""
download_images.py — bulk image downloader + manifest generator

Usage:
    python3 download_images.py --input images.json --outdir ./out [--min-side 100] [--delay 0.3]

Reads a JSON array of image descriptors and downloads each image, deduplicating
by URL (after fragment removal) and by SHA-256 content hash.  Writes a
manifest.json into the output root.  Re-running is idempotent: URLs already
recorded in the manifest are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

# Pillow is the only third-party dependency
try:
    from PIL import Image, UnidentifiedImageError
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    print(
        "WARNING: Pillow not installed.  Image dimensions will not be checked "
        "and thumbnail_candidate will always be False.",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT_S = 15
_MAX_RETRIES = 1

# Categories for which the min-side filter is bypassed
_EXEMPT_CATEGORIES = {"logo", "favicon"}

# Reading defaults to PENDING for every downloaded image except brand marks.
# Rationale: the crawler's `category` guess is unreliable (event banners have
# arrived tagged "homepage"), so we do NOT gate reading on it. read_images.py's
# vision `image_class` is the real router and is cheap + parallel — reading a
# decorative image just labels it "decorative-or-stock", it doesn't act on it.
# The alternative (trusting category) silently drops the one banner that had the
# price. Only logos/favicons — pure brand assets with no embedded data — skip.
_NO_READ_CATEGORIES = {"logo", "favicon"}

# Categories eligible for thumbnail_candidate
_THUMBNAIL_CATEGORIES = {"people", "offering", "facility", "hero"}
_THUMBNAIL_MIN_SIDE = 400

# ── aspect gate (the layout-breaker guard) ───────────────────────────────────
# A card layout in this framework renders `w-full object-cover` with NO aspect
# constraint, so the SOURCE image's ratio becomes the card's height. A Korean
# clinic site is full of page-section strips (1000x4086, 800x9632 …) that pass a
# min-side check and then blow a card to thousands of pixels tall, dragging its
# whole grid row with it. Ratio is therefore a HARD gate, not a preference:
# anything outside this band cannot be a thumbnail as-is (it can still be
# DERIVED into one — see `--derive-thumbs`).
_THUMB_MAX_RATIO = 1.6  # height / width — taller than 8:5 is out
_THUMB_MIN_RATIO = 0.5  # wider than 2:1 is out (banner strips)


def _aspect_ok(width: int | None, height: int | None) -> bool:
    if not width or not height:
        return False
    return _THUMB_MIN_RATIO <= (height / width) <= _THUMB_MAX_RATIO

# MIME-type → file extension mapping (for types not in mimetypes stdlib)
_MIME_EXT_MAP: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/avif": ".avif",
    "image/heic": ".heic",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_url(url: str) -> str:
    """Remove fragment (#...) from a URL."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def _safe_filename(name: str, max_len: int = 60) -> str:
    """Turn an arbitrary string into a filesystem-safe name component."""
    name = re.sub(r"[^\w\-.]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_.")
    return name[:max_len] if name else "image"


def _ext_from_content_type(content_type: str | None) -> str:
    """Derive a file extension from a Content-Type header value."""
    if not content_type:
        return ""
    mime = content_type.split(";")[0].strip().lower()
    if mime in _MIME_EXT_MAP:
        return _MIME_EXT_MAP[mime]
    ext = mimetypes.guess_extension(mime)
    return ext if ext else ""


def _ext_from_url(url: str) -> str:
    """Extract a file extension from the URL path."""
    path = urllib.parse.urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower() if ext else ""


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reading_status(category: str, alt: str, local_path: str) -> str:
    # Default to pending; only pure brand marks skip. The vision reader classifies
    # the rest (image_class) — we don't rely on the crawler's category guess.
    if category in _NO_READ_CATEGORIES:
        return "skipped"
    return "pending"


def _thumbnail_candidate(category: str, width: int | None, height: int | None) -> bool:
    """Can this image sit in a card AS-IS?

    Three gates, all hard: the right KIND of asset, big enough, and a ratio a card
    can hold. This is only the FIRST pass — vision has not run yet, so a logo or a
    text-baked price poster can still slip through on geometry alone. `read_images.py
    --regrade` closes that after the readings exist.
    """
    if category not in _THUMBNAIL_CATEGORIES:
        return False
    if width is None or height is None:
        return False
    if min(width, height) < _THUMBNAIL_MIN_SIDE:
        return False
    return _aspect_ok(width, height)


def _get_image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Return (width, height) using Pillow, or (None, None) on failure."""
    if not _PIL_AVAILABLE:
        return None, None
    try:
        import io
        with Image.open(io.BytesIO(data)) as img:
            return img.size  # (width, height)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------


def _fetch(url: str) -> tuple[bytes, str | None]:
    """
    Download *url* and return (body_bytes, content_type_or_None).
    Raises urllib.error.URLError or OSError on failure.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": _BROWSER_UA}
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        content_type = resp.headers.get("Content-Type")
        return resp.read(), content_type


def _fetch_with_retry(url: str) -> tuple[bytes, str | None]:
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return _fetch(url)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(1)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load existing manifest or return empty structure."""
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"items": [], "by_src": {}, "by_sha256": {}}


def _save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    # Write only the items list (not the index dicts) to disk
    out = {"items": manifest["items"]}
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _build_index(manifest: dict[str, Any]) -> None:
    """Rebuild in-memory lookup dicts from the items list."""
    manifest["by_src"] = {item["src"]: item for item in manifest["items"]}
    manifest["by_sha256"] = {
        item["sha256"]: item for item in manifest["items"] if item.get("sha256")
    }


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process(
    descriptors: list[dict[str, Any]],
    outdir: Path,
    min_side: int,
    delay: float,
) -> None:
    images_root = outdir / "images"
    manifest_path = outdir / "manifest.json"

    # Load (or initialise) the manifest
    manifest = _load_manifest(manifest_path)
    _build_index(manifest)

    # --- Stats ---
    stats: dict[str, int] = {
        "total": 0,
        "success": 0,
        "duplicate_url": 0,
        "duplicate_hash": 0,
        "skipped_size": 0,
        "failed": 0,
    }
    category_counts: dict[str, int] = {}
    failed_urls: list[str] = []

    # --- First pass: URL-based dedup (also skipping already-manifested) ---
    seen_urls: dict[str, str] = {}  # normalised_url -> first raw url
    deduped: list[dict[str, Any]] = []
    for item in descriptors:
        raw_src = item.get("src", "").strip()
        if not raw_src:
            continue
        norm = _normalize_url(raw_src)
        if norm in seen_urls:
            stats["duplicate_url"] += 1
            continue
        if norm in manifest["by_src"]:
            # Already downloaded in a previous run — add alias if needed
            existing = manifest["by_src"][norm]
            if raw_src not in existing.get("aliases", []) and raw_src != norm:
                existing.setdefault("aliases", []).append(raw_src)
            stats["duplicate_url"] += 1
            continue
        seen_urls[norm] = raw_src
        deduped.append({**item, "_norm_src": norm})

    stats["total"] = len(deduped)

    for idx, item in enumerate(deduped):
        norm_src: str = item["_norm_src"]
        category: str = item.get("category", "uncategorized")
        alt: str = item.get("alt", "")
        page: str = item.get("page", "")
        matched_entity: str | None = item.get("matched_entity") or None

        # Download
        try:
            data, content_type = _fetch_with_retry(norm_src)
        except Exception as exc:
            stats["failed"] += 1
            failed_urls.append(norm_src)
            print(f"  FAIL  {norm_src!r}: {exc}", file=sys.stderr)
            if idx < len(deduped) - 1:
                time.sleep(delay)
            continue

        # SHA-256 dedup
        sha256 = _sha256_of(data)
        if sha256 in manifest["by_sha256"]:
            existing = manifest["by_sha256"][sha256]
            if norm_src not in existing.get("aliases", []):
                existing.setdefault("aliases", []).append(norm_src)
            manifest["by_src"][norm_src] = existing
            stats["duplicate_hash"] += 1
            if idx < len(deduped) - 1:
                time.sleep(delay)
            continue

        # Image dimensions
        width, height = _get_image_dimensions(data)

        # Min-side filter (exempt: logo, favicon)
        if (
            _PIL_AVAILABLE
            and category not in _EXEMPT_CATEGORIES
            and width is not None
            and height is not None
            and min(width, height) < min_side
        ):
            stats["skipped_size"] += 1
            if idx < len(deduped) - 1:
                time.sleep(delay)
            continue

        # Determine extension
        ext = _ext_from_content_type(content_type) or _ext_from_url(norm_src) or ".bin"

        # Build safe filename
        url_basename = os.path.basename(urllib.parse.urlparse(norm_src).path)
        base_no_ext, _ = os.path.splitext(url_basename)
        safe_base = _safe_filename(base_no_ext or "image")
        short_hash = sha256[:8]
        filename = f"{short_hash}_{safe_base}{ext}"

        # Save file
        cat_dir = images_root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        dest = cat_dir / filename
        dest.write_bytes(data)

        local_rel = str(dest.relative_to(outdir))

        # Build manifest entry
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "src": norm_src,
            "aliases": [],
            "local": local_rel,
            "category": category,
            "width": width,
            "height": height,
            "bytes": len(data),
            "sha256": sha256,
            "page": page,
            "alt": alt,
            "matched_entity": matched_entity,
            "reading": {
                "status": _reading_status(category, alt, filename)
            },
            "thumbnail_candidate": _thumbnail_candidate(category, width, height),
        }

        manifest["items"].append(entry)
        manifest["by_src"][norm_src] = entry
        manifest["by_sha256"][sha256] = entry

        stats["success"] += 1
        category_counts[category] = category_counts.get(category, 0) + 1

        if idx < len(deduped) - 1:
            time.sleep(delay)

    # Persist manifest
    _save_manifest(manifest_path, manifest)

    # --- Summary ---
    print("\n=== Download summary ===")
    print(f"  Total attempted : {stats['total']}")
    print(f"  Success         : {stats['success']}")
    print(f"  Duplicate URL   : {stats['duplicate_url']}")
    print(f"  Duplicate hash  : {stats['duplicate_hash']}")
    print(f"  Skipped (size)  : {stats['skipped_size']}")
    print(f"  Failed          : {stats['failed']}")
    if category_counts:
        print("\nCategory breakdown (new downloads):")
        for cat, cnt in sorted(category_counts.items()):
            print(f"  {cat:<20} {cnt}")
    if failed_urls:
        print(f"\nFailed URLs ({len(failed_urls)}):")
        for u in failed_urls:
            print(f"  {u}")
    print(f"\nManifest: {manifest_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Bulk-download images described in a JSON file and produce a "
            "de-duplicated manifest."
        )
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="IMAGES_JSON",
        help="Path to input JSON array file",
    )
    parser.add_argument(
        "--outdir", "-o",
        required=True,
        metavar="DIR",
        help="Root output directory (images/ and manifest.json go here)",
    )
    parser.add_argument(
        "--min-side",
        type=int,
        default=100,
        metavar="PX",
        help="Skip images whose shortest side is below this (default: 100; "
             "ignored for logo/favicon categories)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        metavar="SECS",
        help="Seconds to wait between requests (default: 0.3)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"ERROR: input file not found: {input_path}")

    try:
        with input_path.open("r", encoding="utf-8") as f:
            descriptors = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f"ERROR: could not parse input JSON: {exc}")

    if not isinstance(descriptors, list):
        sys.exit("ERROR: input JSON must be a top-level array")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    process(
        descriptors=descriptors,
        outdir=outdir,
        min_side=args.min_side,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
