#!/usr/bin/env python3
"""
read_images.py — Gemini vision batch image reader for org-scrape Phase 2.

Reads images listed in a scrape manifest and uses Gemini's vision API to
extract structured data (prices, events, treatment info) from hospital
website images that embed text as graphics.

Usage:
    python3 read_images.py --manifest .scrape-out/slug/manifest.json \\
        --outdir .scrape-out/slug [--model gemini-3.5-flash] \\
        [--limit N] [--concurrency 8] [--only-pending]

Two jobs per image, in one call:
  1. CLASSIFY — what the image IS (image_class), so the compile step can route it
     to the right entity (doctor→person, banner→promotion, interior→facility …).
  2. EXTRACT — the data embedded as graphics (prices, promotion terms, OCR text).

Speed: images are read CONCURRENTLY via a thread pool (--concurrency). This is
wall-clock parallelism, NOT Gemini's async Batch API (that trades latency — up to
24h — for cost, the opposite of what a scrape run wants).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMINI_API_BASE = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/{model}:generateContent?key={key}"
)

# image_class — what the image IS (for the compile step's entity routing).
# kind — the DATA-bearing role (drives price/promotion extraction).
IMAGE_CLASSES = [
    "doctor-photo",        # a named doctor / staff portrait → person entity
    "staff-group",         # team / group shot
    "facility-interior",   # reception, treatment room, building → facility
    "device-equipment",    # a laser/machine → treatment reference
    "before-after",        # before/after comparison → case
    "procedure-photo",     # a treatment in action
    "event-banner",        # promotion/event graphic (usually has price/period)
    "price-table",         # a price list rendered as an image
    "treatment-info",      # a treatment explainer (text-as-graphic)
    "logo",                # brand mark / wordmark
    "decorative-or-stock", # generic stock / decorative, not org-specific
    "other",
]

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # What the image IS — for entity matching/categorization.
        "image_class": {"type": "string", "enum": IMAGE_CLASSES},
        # The data-bearing role — drives extraction.
        "kind": {
            "type": "string",
            "enum": ["price-table", "event-banner", "treatment-info", "photo", "other"],
        },
        "has_text": {"type": "boolean"},
        # If the image depicts/labels a specific entity, name it (doctor name,
        # treatment name, device model) — helps the compile step match to an entity.
        "subject": {"type": "string"},
        "text_raw": {"type": "string"},
        "prices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "treatment": {"type": "string"},
                    "price": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["treatment", "price", "note"],
            },
        },
        "promotion": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "period": {"type": "string"},
                "benefit": {"type": "string"},
                "condition": {"type": "string"},
            },
            "required": ["name", "period", "benefit", "condition"],
        },
        "summary": {"type": "string"},
    },
    "required": [
        "image_class", "kind", "has_text", "subject",
        "text_raw", "prices", "promotion", "summary",
    ],
}

PROMPT_KO = (
    "이 이미지는 병원/의원 웹사이트의 이미지다. 두 가지를 하라.\n"
    "1) 이미지가 무엇인지 분류하라 (image_class): 의료진 사진(doctor-photo)·"
    "단체 사진(staff-group)·시설 내부(facility-interior)·장비(device-equipment)·"
    "전후 비교(before-after)·시술 장면(procedure-photo)·이벤트 배너(event-banner)·"
    "가격표(price-table)·시술 설명(treatment-info)·로고(logo)·"
    "장식/스톡(decorative-or-stock)·기타(other).\n"
    "2) 이미지 안 텍스트를 모두 읽어라. 특정 대상(의사 이름·시술명·장비 모델)이 "
    "있으면 subject에 적어라. 가격이 있으면 시술명·가격을, 이벤트면 "
    "이벤트명/기간/혜택/조건을 추출하라. kind는 데이터 성격(price-table/"
    "event-banner/treatment-info/photo/other). 텍스트가 없으면 has_text=false."
)

MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# ---------------------------------------------------------------------------
# .env.local parser — no shell export dependency
# ---------------------------------------------------------------------------


def load_env_local(env_path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from a .env file. Ignores comments and blanks."""
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        result[key] = val
    return result


def find_api_key() -> str:
    """
    Locate GEMINI_API_KEY from ${CLAUDE_SKILL_DIR}/.env.local.
    Falls back to GOOGLE_GENERATIVE_AI_API_KEY, then to process env vars.
    """
    skill_dir_env = os.environ.get("CLAUDE_SKILL_DIR")
    if skill_dir_env:
        env_path = Path(skill_dir_env) / ".env.local"
    else:
        # script lives at <skill_dir>/scripts/read_images.py
        env_path = Path(__file__).resolve().parent.parent / ".env.local"

    env_vars = load_env_local(env_path)

    key = (
        env_vars.get("GEMINI_API_KEY")
        or env_vars.get("GOOGLE_GENERATIVE_AI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            f"GEMINI_API_KEY not found in {env_path} or process environment"
        )
    return key


# ---------------------------------------------------------------------------
# Image encoding
# ---------------------------------------------------------------------------


def mime_for_path(path: Path) -> str:
    return MIME_MAP.get(path.suffix.lower(), "image/jpeg")


def encode_image(path: Path) -> tuple[str, str]:
    """Return (base64_data, mime_type) for a local image file."""
    data = path.read_bytes()
    return base64.b64encode(data).decode("ascii"), mime_for_path(path)


# ---------------------------------------------------------------------------
# Gemini API call
# ---------------------------------------------------------------------------


def call_gemini(
    api_key: str,
    model: str,
    b64_data: str,
    mime_type: str,
) -> dict[str, Any]:
    """POST to Gemini generateContent and return the parsed JSON result."""
    url = GEMINI_API_BASE.format(model=model, key=api_key)

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data,
                        }
                    },
                    {"text": PROMPT_KO},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0,
        },
    }

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")

    response_obj = json.loads(raw)
    text = response_obj["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def call_gemini_with_retry(
    api_key: str,
    model: str,
    b64_data: str,
    mime_type: str,
) -> dict[str, Any]:
    """Wrap call_gemini with a single retry on 429 / 5xx responses."""
    try:
        return call_gemini(api_key, model, b64_data, mime_type)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 500, 502, 503, 504):
            time.sleep(2)
            return call_gemini(api_key, model, b64_data, mime_type)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Gemini vision batch image reader for org-scrape Phase 2"
    )
    p.add_argument("--manifest", required=True, help="Path to manifest.json")
    p.add_argument(
        "--outdir",
        required=True,
        help="Scrape output directory (image paths in manifest are relative to this)",
    )
    p.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model name (default: gemini-2.5-flash)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of images to process",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Number of images read in parallel (default: 8). Wall-clock speedup.",
    )
    p.add_argument(
        "--only-pending",
        action="store_true",
        help="Only process items where reading.status == 'pending'",
    )
    p.add_argument(
        "--regrade",
        action="store_true",
        help=(
            "Do not read anything — re-grade `thumbnail_candidate` on the existing "
            "readings and exit. Run this after a full read pass."
        ),
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Thumbnail re-grade (second pass — needs the vision readings)
# ---------------------------------------------------------------------------

# What a card must never show. `download_images.py` gates on geometry alone
# (category + size + ratio) because it runs BEFORE vision; these classes are only
# knowable after a reading, and each one produced a real defect on a live build:
#   logo            → the clinic's logo rendered in a doctor's portrait slot
#   price-table     → a price grid shrunk into a card, unreadable
#   treatment-info  → a whole page section captured as one strip
#   decorative-or-stock → filler that says nothing about the card
_CLASS_BLOCK = {"logo", "price-table", "treatment-info", "decorative-or-stock"}

# Text baked into the image duplicates the card's own heading/description and
# turns to mush at thumbnail size. Not fatal on its own — a device shot with a
# small wordmark is fine — so it downgrades rather than blocks, EXCEPT on classes
# whose whole content is text.
_CLASS_TEXT_FATAL = {"event-banner"}


def regrade_thumbnails(manifest: dict, readings_dir: Path) -> dict[str, int]:
    """Demote thumbnail candidates that vision proved unusable. Returns counts."""
    stats = {"kept": 0, "blocked_class": 0, "blocked_text": 0, "no_reading": 0}
    for item in manifest.get("items", []):
        if not item.get("thumbnail_candidate"):
            continue
        rf = readings_dir / f"{item['id']}.json"
        if not rf.exists():
            stats["no_reading"] += 1
            continue
        try:
            r = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            stats["no_reading"] += 1
            continue
        cls = r.get("image_class")
        reason = None
        if cls in _CLASS_BLOCK:
            reason, key = f"class:{cls}", "blocked_class"
        elif cls in _CLASS_TEXT_FATAL and r.get("has_text"):
            reason, key = f"text-in-{cls}", "blocked_text"
        if reason:
            item["thumbnail_candidate"] = False
            item["thumbnail_blocked"] = reason
            stats[key] += 1
        else:
            # Carry the signals forward so the build can rank candidates.
            item["image_class"] = cls
            item["has_text"] = bool(r.get("has_text"))
            stats["kept"] += 1
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    manifest_path = Path(args.manifest).resolve()
    outdir = Path(args.outdir).resolve()
    readings_dir = outdir / "readings"
    readings_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest
    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)

    items: list[dict[str, Any]] = manifest.get("items", [])

    # Second pass: judge the candidates with what vision already learned, then stop.
    if args.regrade:
        stats = regrade_thumbnails(manifest, readings_dir)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        still = sum(1 for it in items if it.get("thumbnail_candidate"))
        print(
            f"Re-graded thumbnails — kept {stats['kept']}, "
            f"blocked {stats['blocked_class']} by class, {stats['blocked_text']} as text-banner, "
            f"{stats['no_reading']} without a reading. "
            f"Usable thumbnails now: {still}/{len(items)}"
        )
        return

    # Filter to processable candidates
    if args.only_pending:
        candidates = [
            it for it in items if it.get("reading", {}).get("status") == "pending"
        ]
    else:
        # Process everything except explicitly skipped items
        candidates = [
            it for it in items if it.get("reading", {}).get("status") != "skipped"
        ]

    if args.limit is not None:
        candidates = candidates[: args.limit]

    print(f"Candidates: {len(candidates)}  (manifest total: {len(items)})")

    # Resolve API key once
    try:
        api_key = find_api_key()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Build id→item index for O(1) manifest updates
    id_to_item: dict[str, dict[str, Any]] = {it["id"]: it for it in items}

    # Partition candidates: already-done (skip) vs to-process.
    to_process: list[dict[str, Any]] = []
    skipped = 0
    for item in candidates:
        reading_file = readings_dir / f"{item['id']}.json"
        if item.get("reading", {}).get("status") == "done" and reading_file.exists():
            skipped += 1
        else:
            to_process.append(item)

    # Counters (mutated only in the main thread as futures complete)
    succeeded = 0
    failed = 0
    errors: list[dict[str, str]] = []
    kind_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    price_image_count = 0
    manifest_lock = threading.Lock()

    def read_one(item: dict[str, Any]) -> dict[str, Any]:
        """Worker: read a single image. Returns a result dict (thread-safe — no
        shared state mutated here; only reads args/api_key and returns)."""
        item_id: str = item["id"]
        local_rel: str = item.get("local", "")
        img_path = outdir / local_rel
        if not img_path.exists():
            return {"id": item_id, "local": local_rel, "error": "image file not found"}
        try:
            b64_data, mime_type = encode_image(img_path)
            result = call_gemini_with_retry(api_key, args.model, b64_data, mime_type)
        except Exception as exc:  # noqa: BLE001 — record and continue
            return {"id": item_id, "local": local_rel, "error": str(exc)}
        return {"id": item_id, "local": local_rel, "result": result}

    workers = max(1, args.concurrency)
    print(f"Reading {len(to_process)} images with concurrency={workers} "
          f"(model={args.model})")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(read_one, it): it for it in to_process}
        for fut in as_completed(futures):
            out = fut.result()
            item_id = out["id"]
            local_rel = out.get("local", "")

            if "error" in out:
                errors.append(out)
                failed += 1
                print(f"  FAIL {local_rel}: {out['error']}", file=sys.stderr)
                continue

            result = out["result"]
            kind: str = result.get("kind", "other")
            image_class: str = result.get("image_class", "other")
            prices: list[dict[str, str]] = result.get("prices", [])
            promotion: dict[str, str] = result.get(
                "promotion", {"name": "", "period": "", "benefit": "", "condition": ""}
            )
            record: dict[str, Any] = {
                "manifest_id": item_id,
                "read_by": "gemini",
                "model": args.model,
                "image_class": image_class,
                "kind": kind,
                "has_text": result.get("has_text", False),
                "subject": result.get("subject", ""),
                "text_raw": result.get("text_raw", ""),
                "prices": prices,
                "promotion": promotion,
                "summary": result.get("summary", ""),
                "local": local_rel,
            }

            (readings_dir / f"{item_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Manifest update + flush — main thread only, guarded for clarity.
            with manifest_lock:
                id_to_item[item_id]["reading"] = {
                    "status": "done",
                    "result": f"readings/{item_id}.json",
                    "image_class": image_class,
                }
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            class_counts[image_class] = class_counts.get(image_class, 0) + 1
            if prices:
                price_image_count += 1
            succeeded += 1
            print(f"  OK  [{image_class:18s}|{kind:14s}] {local_rel}  "
                  f"(prices={len(prices)})")

    attempted = len(to_process)

    # Final manifest flush (covers zero-item runs)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print(f"Attempted : {attempted}")
    print(f"Succeeded : {succeeded}")
    print(f"Skipped   : {skipped}  (already done)")
    print(f"Failed    : {failed}")
    print()

    if class_counts:
        print("Image class distribution (what each image IS):")
        for k, v in sorted(class_counts.items(), key=lambda x: -x[1]):
            print(f"  {k:<20s} {v}")
        print()

    if kind_counts:
        print("Data-kind distribution:")
        for k, v in sorted(kind_counts.items(), key=lambda x: -x[1]):
            print(f"  {k:<20s} {v}")
        print()

    print(f"Images with extracted prices : {price_image_count}")

    if errors:
        print()
        print(f"Failures ({len(errors)}):")
        for err in errors:
            short_id = err["id"][:8] if "id" in err else "?"
            print(f"  [{short_id}] {err.get('local', '?')} — {err['error']}")


if __name__ == "__main__":
    main()
