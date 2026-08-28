#!/usr/bin/env python3
"""
imagegen.py — landing-page imagery. Generates with Gemini `gemini-3.1-flash-image`
(Nano Banana 2), and pulls a transparent cutout out of ANY image, including one another
generator produced.

Image generation is normally DELEGATED to the higgsfield skills (see ../SKILL.md).

For an ISOLATED cutout, prefer their `image_background_remover`: it returns a real RGBA PNG,
its edges on glass and hair beat the green pass here, and it is one call rather than three.
What stays here is COMPOSITION. That model takes only `medias`, so it cannot place a subject,
and a band image has to be cropped by the bottom edge with transparent headroom above it. So
`--anchor bottom` and `--fill-width`, the flat-art white matte, and the whole no-auth fallback
live in this file. The two jobs are:

  `generate` (aliases: single, batch)
      Direct Gemini generation. The fallback when higgsfield auth is unavailable, and the
      quickest path for a plain set.

  `cutout`
      Take an existing image (a local file or a URL, e.g. a higgsfield result) and return
      a clean RGBA PNG, grounded at the bottom edge if asked. Use it when the subject has to
      sit ON a band; use image_background_remover when it just has to float.

Two orthogonal axes describe every image, and they compose:

  --shot   WHAT it depicts and how it is framed (shots.json). Composition, subject rules,
           the per-item rhythm a batch cycles, and the quality levers that shot needs.
  --style  HOW it feels (styles.json). Palette, light, medium, mood. One style per org.

Rhythm across a set comes from the shot's beats, not from changing style. `--preset` still
works and resolves to a {shot, style} pair through styles.json `_aliases`.

Transparency, when asked for, renders the subject twice: a natural render (A), then the
same subject isolated on a chroma-key GREEN background with A handed back as a reference so
the subject stays identical (B). Alpha comes from B's known key color, and the difference
between A and B rescues genuinely green parts of the subject (they agree across the pair,
real background does not). `cutout` runs only the B half against an image you supply.

Usage
-----
  # one image
  python imagegen.py generate --prompt "a white ceramic pour-over dripper" \
      --shot product-catalog --style editorial-warm --out out/dripper.jpg

  # a cohesive set, one image per item, shared style + per-item rhythm
  python imagegen.py generate --spec jobs.json --shot product-catalog \
      --style editorial-warm --outdir out/

  # alpha out of an image someone else made
  python imagegen.py cutout --image https://.../higgsfield-result.png --out out/x.png
  python imagegen.py cutout --image logo.png --matte-method white --out out/logo.png

  # list the axes
  python imagegen.py shots
  python imagegen.py styles

jobs.json:
  {
    "shared": "product hero shots for a specialty coffee brand's menu",
    "items": [
      {"id": "dripper", "subject": "a white ceramic pour-over dripper"},
      {"id": "grinder", "subject": "a matte black hand coffee grinder"},
      {"id": "beans",   "subject": "a small dish of glossy roasted coffee beans"}
    ]
  }

The API key is read from --key or the GEMINI_API_KEY env var.
"""

import argparse
import base64
import io
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from PIL import Image, ImageFilter

try:
    from scipy import ndimage as _ndi
except Exception:  # cleanup is a nice-to-have; degrade gracefully if scipy is absent
    _ndi = None

HERE = os.path.dirname(os.path.abspath(__file__))
STYLES_PATH = os.path.join(HERE, "styles.json")
SHOTS_PATH = os.path.join(HERE, "shots.json")

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# Defaults required by the skill: every image 2K, square.
IMAGE_SIZE = "2K"
ASPECT = "1:1"

# Chroma-key green used for transparent renders (a flat "spill green" ~#00B140).
KEY_GREEN = (0, 177, 64)


# --------------------------------------------------------------------------- #
# Gemini client
# --------------------------------------------------------------------------- #
def _api_key(cli_key=None):
    key = cli_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("No API key. Pass --key or set GEMINI_API_KEY.")
    return key


def call_gemini(parts, key, *, size=IMAGE_SIZE, aspect=None, max_retries=5):
    """POST one generateContent request. `parts` is a list of Gemini content parts
    (a {"text": ...} and optional {"inlineData": {...}} image inputs). Returns the raw
    bytes of the first returned image. Retries on 429/5xx with server-suggested backoff.
    `aspect` defaults to the module ASPECT (set once from --aspect)."""
    aspect = aspect or ASPECT
    url = ENDPOINT.format(model=MODEL, key=key)
    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": size},
        },
    }).encode()

    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
            return _extract_image(data)
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            last_err = f"HTTP {e.code}: {raw[:400]}"
            if e.code == 429:
                wait = _parse_retry(raw, default=20 * (attempt + 1))
                time.sleep(wait + 0.5)
                continue
            if 500 <= e.code < 600:
                time.sleep(2 ** attempt)
                continue
            break  # 4xx other than 429 won't fix itself
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = str(e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini image call failed after {max_retries} tries. {last_err}")


def _parse_retry(raw, default):
    m = re.search(r"retry in ([\d.]+)s", raw)
    return float(m.group(1)) if m else default


def _extract_image(data):
    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError(f"No candidates. {json.dumps(data)[:400]}")
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline:
            return base64.b64decode(inline["data"])
    finish = cands[0].get("finishReason", "?")
    texts = " ".join(str(p.get("text", "")) for p in parts)
    raise RuntimeError(f"No image in response (finishReason={finish}). {texts[:300]}")


def _as_input_part(img_bytes, mime="image/jpeg"):
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(img_bytes).decode()}}


def _load_ref_part(path):
    return _as_input_part(open(path, "rb").read(), mimetypes.guess_type(path)[0] or "image/jpeg")


def _style_directive(n):
    ref = "image" if n == 1 else f"{n} images"
    return (f"Use the provided {ref} ONLY as a STYLE reference. Reproduce their artistic medium, "
            "texture, GRAIN and NOISE, color palette, soft focus and mood as faithfully as you "
            "can — render heavy film/riso grain, gritty noise, soft blur, haze and abstract, "
            "low-detail softness directly into the image itself. Do NOT sharpen, clean up, "
            "vectorize, flatten, or add crisp fine detail the references do not have; keep forms "
            "soft-edged, grainy and painterly. Include NO text, letters, numbers, captions, "
            "watermarks or signatures anywhere in the image, even if the references contain them. "
            "Do NOT copy the reference's subject matter or composition. Render this subject in "
            "that exact style: ")


def build_parts(text, style_refs):
    """A generation's content parts. With style_refs, the reference images lead and a
    style-transfer directive is prepended to the text — so the model borrows their LOOK
    (medium, palette, grain) while rendering our subject, not their content."""
    if not style_refs:
        return [{"text": text}]
    return [_load_ref_part(p) for p in style_refs] + [{"text": _style_directive(len(style_refs)) + text}]


# --------------------------------------------------------------------------- #
# Prompt composition
# --------------------------------------------------------------------------- #
def _load(path):
    with open(path) as f:
        return json.load(f)


def load_styles():
    return _load(STYLES_PATH)


def load_shots():
    return _load(SHOTS_PATH)


def public_keys(reg):
    return [k for k in reg if not k.startswith("_")]


def resolve_axes(preset=None, shot=None, style=None):
    """Turn whatever the caller named into a (shot, style) pair of dicts, either of which may
    be None. `--preset` is the old single-axis flag: a bare style name still works, and the
    names that were really shot+style bundles resolve through styles.json `_aliases`."""
    shots, styles = load_shots(), load_styles()
    aliases = styles.get("_aliases", {})

    if preset:
        if preset in aliases and not preset.startswith("_"):
            shot = shot or aliases[preset].get("shot")
            style = style or aliases[preset].get("style")
        elif preset in styles and not preset.startswith("_"):
            style = style or preset
        elif preset in shots and not preset.startswith("_"):
            shot = shot or preset
        else:
            sys.exit(f"Unknown --preset '{preset}'. Styles: {', '.join(public_keys(styles))}. "
                     f"Shots: {', '.join(public_keys(shots))}.")

    shot_d = style_d = None
    if shot:
        shot_d = shots.get(shot)
        if shot_d is None or shot.startswith("_"):
            sys.exit(f"Unknown --shot '{shot}'. Options: {', '.join(public_keys(shots))}")
    if style:
        style_d = styles.get(style)
        if style_d is None or style.startswith("_"):
            sys.exit(f"Unknown --style '{style}'. Options: {', '.join(public_keys(styles))}")

    # A shot may prefer a style (icons and logo marks want flat art). Only a default: an
    # explicit --style always wins.
    if shot_d and style_d is None and shot_d.get("style_hint"):
        style_d = styles.get(shot_d["style_hint"])
    return shot_d, style_d


def _shot_aspect(shot, aspect):
    """The ratio a prompt should describe. Explicit wins, then the shot's natural ratio, then
    the module default. Keeping this in one place stops a composer from silently describing a
    square while the API is asked for a wide frame."""
    return aspect or (shot or {}).get("default_aspect") or ASPECT


def _framing_clause(aspect=None):
    """The composition clause appended to every prompt. It MUST agree with the aspect ratio we
    actually request: the old build hardcoded 'square 1:1' even when --aspect 21:9 was passed,
    so the prompt fought the API and wide band images came back centered and cropped."""
    a = (aspect or ASPECT or "1:1").strip()
    tail = "subject fully inside the frame with comfortable margins"
    if a == "1:1":
        return f"square 1:1 composition, {tail}"
    try:
        w, h = (float(x) for x in a.split(":"))
    except ValueError:
        return f"{a} composition, {tail}"
    if w > h:
        wide = "very wide panoramic" if w / h >= 2.4 else "wide landscape"
        return (f"{wide} {a} composition filling the full width of the frame, "
                f"composed for a {a} crop, {tail}")
    return f"vertical portrait {a} composition, composed for a {a} crop, {tail}"


def _quality(shot, extra):
    """The shot's own quality lever plus the caller's --extra. A people shot always needs the
    realism clause, so it is a property of the shot rather than something the caller must
    remember to type."""
    bits = []
    if shot and shot.get("extra"):
        bits.append(shot["extra"].strip().rstrip("."))
    if extra:
        bits.append(extra.strip().rstrip("."))
    return bits


def compose(subject, shared, shot, style, rhythm_index, extra="", aspect=None):
    """Build a prompt: subject first, then the shared context, the shot's framing and the
    rhythm beat for this item's position, the style's palette and light, and the quality
    qualifiers near the end where they read as shot direction."""
    bits = [subject.strip().rstrip(".")]
    if shared:
        bits.append(shared.strip().rstrip("."))
    if shot:
        bits.append(shot["framing"])
        rh = shot.get("rhythm") or []
        if rh and rhythm_index is not None:
            bits.append(rh[rhythm_index % len(rh)])
    if style:
        bits.append(style["common"])
        # A named photographer moves the look further than any number of mood words. It is what
        # higgsfield's own enhancer writes into every brief as [STYLE REFERENCE].
        if style.get("style_reference"):
            bits.append(style["style_reference"])
    bits += _quality(shot, extra)
    bits.append(_framing_clause(_shot_aspect(shot, aspect)))
    return ". ".join(b for b in bits if b) + "."


def compose_isolated(subject, shared, shot, style, extra="", aspect=None):
    """Prompt for a cutout-ready render: a SINGLE object, no props or scenery. A style's full
    `common` can build a whole lit scene, which cannot be cleanly keyed, so for transparency we
    keep only its palette for family cohesion and drop the rest."""
    subj = subject.strip().rstrip(".")
    bits = [f"a single isolated {subj}, alone and centered, the entire object fully visible"]
    if shared:
        bits.append(shared.strip().rstrip("."))
    bits.append("floating in empty space with nothing beneath it, no ground, no surface, no "
                "table, no horizon line, no shadow, no other objects, no props, no hands, no "
                "scenery, plain uniform seamless studio background, soft even lighting")
    if style and style.get("palette"):
        bits.append(f"{style['palette']} color tones")
    bits += _quality(shot, extra)
    bits.append(_framing_clause(_shot_aspect(shot, aspect)))
    return ". ".join(bits) + "."


def compose_grounded(subject, shared, shot, style, extra, open_sides, aspect=None):
    """Prompt for a GROUNDED cutout: the subject sits at the BOTTOM of the frame, cropped by and
    bleeding off the bottom edge (a solid bottom), with transparent headroom above once keyed.
    `open_sides` also opens the left/right (subject centred); otherwise the subject spans the
    full width so only the top is transparent."""
    subj = subject.strip().rstrip(".")
    sides = ("centered with clear empty space on both the left and right sides"
             if open_sides else "spanning the full width across to both side edges")
    bits = [f"a {subj}, composed prominently and fairly large, cropped by the bottom edge so its "
            f"lower part extends beyond the bottom, leaving only a small margin of headroom above "
            f"it, {sides}. EXACTLY ONE {subj} — a single subject, no duplicate, no second copy, no "
            f"mirror image, no reflection, no ghosting. The subject is simply cropped by the frame "
            f"edge — it is NOT standing on a floor or surface"]
    if shared:
        bits.append(shared.strip().rstrip("."))
    bits.append("no floor, no surface, no table, no horizon line, no other objects, no props, no "
                "scenery, plain flat uniform background, soft even lighting")
    if style and style.get("palette"):
        bits.append(f"{style['palette']} color tones")
    bits += _quality(shot, extra)
    bits.append(_framing_clause(_shot_aspect(shot, aspect)))
    return ". ".join(bits) + "."


# --------------------------------------------------------------------------- #
# Transparent background: two renders + difference matting
# --------------------------------------------------------------------------- #
def _to_float(img_bytes):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.asarray(im, dtype=np.float32) / 255.0, im.size


def _smoothstep(lo, hi, x):
    t = np.clip((x - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _keep_cored_regions(alpha, presence=0.08, core=0.6):
    """Drop connected alpha regions that have no SOLID core. A real subject (and each
    separate part of it — a wordmark's letters, a dot on an 'i') has opaque interior;
    leftover keying haze/bands are all partial alpha and get removed. Regions of a soft
    subject (steam, hair) stay because they connect to the subject's solid core."""
    if _ndi is None:
        return alpha
    lbl, n = _ndi.label(alpha > presence)
    if n == 0:
        return alpha
    keep = np.unique(lbl[alpha > core])
    keep = keep[keep != 0]
    return np.where(np.isin(lbl, keep), alpha, 0.0)


def _keep_bottom_connected(rgba):
    """For a GROUNDED cutout the true subject reaches the bottom edge; anything floating in the
    headroom (a mis-rendered ghost/double of the subject, stray haze) does not. Keep only alpha
    components that touch the bottom band, dropping the rest — kills the ghosting the green
    two-render occasionally produces on large faces."""
    if _ndi is None:
        return rgba
    a = np.asarray(rgba).copy()
    lbl, n = _ndi.label(a[..., 3] > 26)
    if n == 0:
        return rgba
    keep = np.unique(lbl[-3:, :])  # components present in the bottom 3 rows
    keep = keep[keep != 0]
    if keep.size == 0:
        return rgba
    a[..., 3] = np.where(np.isin(lbl, keep), a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


def matte(a_bytes, b_bytes, method="diff"):
    """Recover an RGBA cutout. B is the subject on a flat green key (its background is a
    KNOWN color, so it keys cleanly); A is the natural render. `greenness` measures how
    key-colored each B pixel is; `disagree` measures |A-B| (real background differs across
    the pair, the subject does not). Background = key-colored AND disagreeing, so a green
    PART OF THE SUBJECT (agrees with A) is kept. RGB comes from B with green-spill removed,
    so color and alpha stay self-consistent (no edge ghosting)."""
    a, _ = _to_float(a_bytes)
    b, size = _to_float(b_bytes)
    if a.shape != b.shape:  # ref-guided B can come back at a different size
        a = np.asarray(Image.fromarray((a * 255).astype("uint8")).resize(size), np.float32) / 255.0

    R, G, Bl = b[..., 0], b[..., 1], b[..., 2]
    # How much this pixel looks like the green key: green dominates red & blue. We take the
    # max of an ABSOLUTE excess (catches bright flat key) and a RELATIVE excess normalized by
    # brightness (catches the DARK green of a cast shadow the model sometimes paints on the
    # key — its absolute excess is small but it's still clearly green-dominant).
    g_abs = np.clip(G - np.maximum(R, Bl), 0.0, 1.0)
    g_rel = g_abs / np.clip(G, 1e-3, 1.0)
    green_conf = np.maximum(_smoothstep(0.04, 0.30, g_abs),
                            _smoothstep(0.12, 0.55, g_rel))  # 0 = subject, 1 = key background

    if method == "diff":
        disagree = _smoothstep(0.05, 0.25, np.abs(a - b).mean(axis=2))
        # The difference term exists to RESCUE genuinely green parts of the subject, which agree
        # across the pair. It must not also gate the flat key itself: a grey in A whose bright-
        # ness sits near the key's own distance-minimum (a spotlight gradient, a smoke wisp)
        # scores |A-B| just under the threshold, so `disagree` dips and a ghost of the backdrop
        # mattes through at roughly 15% alpha, joined to the subject by partial alpha so no
        # component filter can drop it. Where B is the key colour beyond doubt, it is background
        # whatever A looked like. The key's green excess (about 0.44) sits far above any natural
        # subject green (a lime reaches about 0.20), so the raw excess separates them cleanly.
        unambiguous = _smoothstep(0.30, 0.42, g_abs)
        bg = green_conf * np.maximum(disagree, unambiguous)
    else:  # pure chroma key
        bg = green_conf
    alpha = 1.0 - bg

    # De-speckle + feather (radii scaled for 2K).
    a_im = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype("uint8"), "L")
    a_im = a_im.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    alpha = np.asarray(a_im, np.float32) / 255.0
    alpha = _keep_cored_regions(alpha)  # remove keying haze that has no solid subject behind it

    # Green-spill suppression: where the subject picked up green light, pull G down to the
    # neighbouring channels so edges don't fringe green once composited.
    rgb = b.copy()
    spill = np.clip(G - np.maximum(R, Bl), 0.0, 1.0)
    rgb[..., 1] = G - spill * 0.9

    out = np.dstack([np.clip(rgb, 0, 1), alpha])
    return Image.fromarray((out * 255).astype("uint8"), "RGBA")


_B_BASE = (
    "Take the subject from the provided image — keep its shape, colors, materials, pose and "
    "lighting EXACTLY — and place it, floating and fully isolated, on a background of vivid "
    "saturated pure chroma-key green (RGB 0,177,64), the exact green of a studio green screen. "
    "Replace EVERYTHING that is not the subject with this green: ignore the reference image's "
    "background entirely. Nothing beneath the subject: no table, no surface, no floor, no wall, "
    "no horizon line, no gradient, no scenery, no props, no cast shadow and no reflection. The "
    "flat green must reach all four edges, including the very bottom of the frame. The subject "
    "stays inside the frame with even margins."
)
_B_STRONG = (
    "GREEN SCREEN CUTOUT. The subject from the provided image floats in the exact center on a "
    "100% uniform, flat, VIVID pure green screen (RGB 0,177,64) — the loud saturated green used "
    "for chroma keying, NOT a pale or grey-green. Every single pixel that is not the subject is "
    "this one green, all the way to every edge and corner. Absolutely no surface, table, floor, "
    "shadow, reflection, or gradient. Keep the subject's silhouette, colors and details identical "
    "to the reference."
)


def _b_grounded(open_sides, strong=False):
    """The green re-render prompt for a bottom-anchored cutout: green fills the headroom (and
    sides if open), the subject reaches and is cropped by the bottom edge so the bottom stays
    opaque once keyed."""
    where = ("the entire area above the subject (the headroom) AND on both sides of it"
             if open_sides else "the entire area above the subject (the headroom)")
    core = (
        "Take the subject from the provided image — keep its shape, colors, materials, pose and "
        "lighting EXACTLY. Place it LOW in the frame, cropped by the bottom edge so its lower part "
        "extends beyond the bottom (it is cropped by the FRAME, NOT standing on a floor or surface). "
        "Fill the entire rest of the background — " + where + ", and directly behind the subject — "
        "with ONE flat, uniform, vivid pure chroma-key green (RGB 0,177,64), the exact green of a "
        "studio green screen. There is NO floor, NO surface, NO horizon line, NO gradient, NO "
        "shadow and NO reflection — just flat green everywhere the subject is not. Render EXACTLY "
        "ONE subject — no duplicate, no mirrored copy, no ghost. The subject stays cropped by the "
        "bottom edge so there is no green gap below it.")
    if strong:
        core += (" Make the green LOUD, flat, saturated and 100% uniform — not pale, grey or "
                 "graduated — every pixel that is not the subject is this one green.")
    return core


def _edge_green_fracs(b_bytes):
    """Green fraction of each edge band, plus the bottom-CENTER (where a grounded subject should
    sit) — how much of each region the model actually keyed green."""
    im = Image.open(io.BytesIO(b_bytes)).convert("RGB")
    a = np.asarray(im, np.float32) / 255.0
    h, w = a.shape[:2]
    fr = max(16, min(h, w) // 40)
    band = lambda x: float(((x[..., 1] - np.maximum(x[..., 0], x[..., 2])) > 0.12).mean())
    return {"top": band(a[:fr]), "bottom": band(a[-fr:]),
            "left": band(a[:, :fr]), "right": band(a[:, -fr:]),
            "bottom_center": band(a[-fr:, int(w * 0.3):int(w * 0.7)]),
            # Edge bands alone miss a patch of un-keyed backdrop sitting INSIDE the frame,
            # which mattes through as a ghost smudge attached to the subject by a thread of
            # partial alpha, so no component filter can drop it. The whole-frame fraction is
            # what notices, and lets us retry for a cleaner green pass.
            "frame": band(a)}


def _anchor_score(fr, anchor, open_sides):
    """Quality of a B render for the requested layout. float: all four edges green. bottom: the
    headroom (and sides, if open) is green AND the subject reaches the bottom-center (that patch
    is NOT green), which is what makes the bottom edge solid."""
    if anchor == "float":
        # A floating cutout is ONE isolated object with margins, so the background is most of
        # the frame. Anything under about 55% green means a chunk of the original backdrop
        # survived somewhere inside, even when all four edges keyed cleanly.
        return min(fr["top"], fr["bottom"], fr["left"], fr["right"]) * float(
            _smoothstep(0.40, 0.60, fr["frame"]))
    want = [fr["top"]] + ([fr["left"], fr["right"]] if open_sides else [])
    # grounded is satisfied as long as the subject is PRESENT at the bottom-center; a narrow
    # subject leaves green beside it there, which is fine, so only penalize a near-fully-green
    # bottom (subject floating / absent).
    grounded = 1.0 - float(_smoothstep(0.6, 0.95, fr["bottom_center"]))
    return min(want) * grounded


def matte_white(a_bytes):
    """For FLAT art (logos, icons): render once on white, key the whiteness. Flat graphics are
    ink/color on a light ground, so distance-from-white IS the alpha — no green pass, no
    model-invented surface to fight, and it's a single cheap render. Cored cleanup drops any
    stray light-grey container edges the model added around the mark."""
    a, _ = _to_float(a_bytes)
    dist = 1.0 - a.min(axis=2)  # white → 0 ; any ink or saturated color → > 0
    alpha = _smoothstep(0.06, 0.22, dist)
    a_im = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype("uint8"), "L")
    a_im = a_im.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    alpha = _keep_cored_regions(np.asarray(a_im, np.float32) / 255.0, presence=0.06, core=0.5)
    return Image.fromarray((np.dstack([np.clip(a, 0, 1), alpha]) * 255).astype("uint8"), "RGBA")


#: Ratios the image API accepts. The green re-render must be requested at the SAME ratio as the
#: image it is keying, or the two frames do not line up and the difference matte is garbage.
SUPPORTED_ASPECTS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9",
                     "1:4", "4:1", "1:8", "8:1"]


def _nearest_aspect(w, h):
    """The supported ratio closest to a real pixel size, compared in log space so 16:9 and 9:16
    are equally far from square."""
    target = np.log(w / max(h, 1))
    best, best_d = "1:1", float("inf")
    for a in SUPPORTED_ASPECTS:
        aw, ah = (float(x) for x in a.split(":"))
        d = abs(np.log(aw / ah) - target)
        if d < best_d:
            best, best_d = a, d
    return best


def cutout_from(a_bytes, key, matte_method="diff", debug_dir=None, tag="img", bg_retries=3,
                anchor="bottom", open_sides=True, aspect_exact=None):
    """Pull an RGBA cutout out of an ALREADY-RENDERED image. This is the half of the pipeline
    that does not care who generated `a_bytes`, so it works on a higgsfield result, a photo the
    customer sent, or our own render. The subject is re-rendered onto a green key with `a_bytes`
    handed back as reference, then matted.

    `anchor="float"` = fully isolated cutout (all sides transparent). `anchor="bottom"` (default)
    = the subject grounds at the bottom edge (solid bottom) with transparent headroom.
    `open_sides` (default True) keeps left and right transparent, which is right for a narrow
    subject; set it False only for a subject that fills the frame width. The white method needs
    no second render and ignores anchor."""
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        open(os.path.join(debug_dir, f"{tag}_A.jpg"), "wb").write(a_bytes)

    if matte_method == "white":
        return crop_to_aspect(matte_white(a_bytes), aspect_exact) if aspect_exact else matte_white(a_bytes)

    # Key the green pass at whatever ratio the source actually is, not the module default.
    src_w, src_h = Image.open(io.BytesIO(a_bytes)).size
    b_aspect = _nearest_aspect(src_w, src_h)

    b_prompts = ([_B_BASE, _B_STRONG] if anchor == "float"
                 else [_b_grounded(open_sides), _b_grounded(open_sides, strong=True)])
    best_b, best_score = None, -1.0
    for i in range(max(1, bg_retries)):
        b = call_gemini([{"text": b_prompts[min(i, 1)]}, _as_input_part(a_bytes)], key,
                        aspect=b_aspect)
        score = _anchor_score(_edge_green_fracs(b), anchor, open_sides)
        if score > best_score:
            best_b, best_score = b, score
        if score >= 0.85:
            break
    if debug_dir:
        open(os.path.join(debug_dir, f"{tag}_B.jpg"), "wb").write(best_b)
    if best_score < 0.5:
        print(f"  [warn] [{tag}] weak green background (score={best_score:.2f}); cutout may be rough")
    rgba = matte(a_bytes, best_b, method=matte_method)
    if aspect_exact:
        rgba = crop_to_aspect(rgba, aspect_exact)
    if anchor == "bottom":
        rgba = _keep_bottom_connected(rgba)  # drop floating ghosts in the headroom
    return rgba


def gen_transparent(subject, shared, shot, style, rhythm_index, key, matte_method="diff",
                    debug_dir=None, tag="img", bg_retries=3, style_refs=None, extra="",
                    anchor="bottom", open_sides=True, aspect=None):
    """Generate the A render ourselves, then hand it to `cutout_from`. Use this when we are
    generating; use `cutout_from` directly when someone else already made the image."""
    if matte_method == "white":  # flat-art / logo path: one white render, key the white
        a_prompt = compose_isolated(subject, shared, shot, style, extra, aspect).rstrip(".") + (
            ". On a pure solid white background, no frame, no border, no container, no badge, "
            "no shadow, no gradient.")
    elif anchor == "float":      # fully isolated cutout, all four sides transparent
        a_prompt = compose_isolated(subject, shared, shot, style, extra, aspect)
    else:                        # bottom-anchored: solid bottom + transparent headroom
        a_prompt = compose_grounded(subject, shared, shot, style, extra, open_sides, aspect)

    a_bytes = call_gemini(build_parts(a_prompt, style_refs), key, aspect=aspect)
    return cutout_from(a_bytes, key, matte_method, debug_dir, tag, bg_retries, anchor, open_sides,
                       aspect_exact=aspect)


# --------------------------------------------------------------------------- #
# Save helpers
# --------------------------------------------------------------------------- #
def crop_to_aspect(im, aspect):
    """Centre-crop to EXACTLY the requested ratio.

    The API takes an aspect ratio as a request, not a contract: asking for 4:5 came back
    1856x2304, which is 0.8056 rather than 0.800. That 0.7% is invisible on its own and
    fatal in a layout, because a card slot with a fixed `aspect-4/5` and `object-contain`
    letterboxes the difference as a pale band above and below. The reference tenant's
    hand-authored assets are exact (1016x1270), which is why their page looks right and a
    generated one does not. Crop rather than resize so nothing is stretched."""
    if not aspect:
        return im
    try:
        aw, ah = (float(x) for x in str(aspect).split(":"))
    except ValueError:
        return im
    w, h = im.size
    want, have = aw / ah, w / h
    if abs(want - have) < 1e-4:
        return im
    if have > want:                      # too wide: trim the sides
        new_w = max(1, round(h * want))
        off = (w - new_w) // 2
        return im.crop((off, 0, off + new_w, h))
    new_h = max(1, round(w / want))      # too tall: trim top and bottom
    off = (h - new_h) // 2
    return im.crop((0, off, w, off + new_h))


def save_opaque(img_bytes, out_path, aspect=None):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im = crop_to_aspect(Image.open(io.BytesIO(img_bytes)).convert("RGB"), aspect)
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        im.save(out_path, "JPEG", quality=92)
    else:
        im.save(out_path, "PNG")
    return im.size


def save_rgba(rgba_im, out_path):
    if not out_path.lower().endswith(".png"):
        out_path = os.path.splitext(out_path)[0] + ".png"  # transparency needs PNG
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    rgba_im.save(out_path, "PNG")
    return out_path


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _read_image(src):
    """Load an image given a local path or an http(s) URL. Delegated generation hands back a
    URL, so `cutout` has to accept both."""
    if src.startswith("http://") or src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=120) as r:
            return r.read()
    with open(src, "rb") as f:
        return f.read()


def _wants_transparent(args, shot):
    """--transparent asks for it outright; a shot whose whole job is a cutout (product-cutout,
    icon-flat, logo-mark) implies it. --opaque forces it off."""
    if getattr(args, "opaque", False):
        return False
    return bool(args.transparent or (shot and shot.get("transparent") == "preferred"))


def _matte_method(args, shot):
    """An explicit --matte-method wins. Otherwise the shot knows: flat art keys off white,
    photographic objects key off green."""
    if args.matte_method:
        return args.matte_method
    return (shot or {}).get("matte_method", "diff")


def _resolved_aspect(args, shot):
    """An explicit --aspect wins, else the shot's natural ratio, else square."""
    return args.aspect or (shot or {}).get("default_aspect") or "1:1"


def _gen_one(subject, rhythm_index, out, args, shot, style, key, tag):
    """Generate one image to `out`. Returns the path actually written (transparency forces PNG)."""
    aspect = _resolved_aspect(args, shot)
    if _wants_transparent(args, shot):
        rgba = gen_transparent(subject, args.shared, shot, style, rhythm_index, key,
                               _matte_method(args, shot), args.debug_dir, tag=tag,
                               bg_retries=args.bg_retries, style_refs=args.style_ref,
                               extra=args.extra, anchor=args.anchor,
                               open_sides=not args.fill_width, aspect=aspect)
        return save_rgba(rgba, out)
    prompt = compose(subject, args.shared, shot, style, rhythm_index, args.extra, aspect)
    img = call_gemini(build_parts(prompt, args.style_ref), key, aspect=aspect)
    save_opaque(img, out, aspect)
    return out


def _run_item(idx, item, args, shot, style, key):
    iid = str(item.get("id", idx))
    subject = item["subject"]
    ext = ".png" if _wants_transparent(args, shot) else ".jpg"
    out = os.path.join(args.outdir, f"{iid}{ext}")
    try:
        written = _gen_one(subject, idx, out, args, shot, style, key, tag=iid)
        return {"id": iid, "ok": True, "file": written, "subject": subject}
    except Exception as e:  # one bad item shouldn't sink the batch
        return {"id": iid, "ok": False, "error": str(e), "subject": subject}


def cmd_generate(args):
    """One image (--prompt/--out) or a cohesive set (--spec/--outdir)."""
    key = _api_key(args.key)
    shot, style = resolve_axes(args.preset, args.shot, args.style)

    if args.spec:
        spec = json.load(open(args.spec))
        args.shared = args.shared or spec.get("shared", "")
        items = spec["items"]
        if not args.outdir:
            sys.exit("--spec needs --outdir")
        os.makedirs(args.outdir, exist_ok=True)
        print(f"batch: {len(items)} items, shot={args.shot or '-'}, style={args.style or '-'}, "
              f"aspect={_resolved_aspect(args, shot)}, "
              f"transparent={_wants_transparent(args, shot)}, concurrency={args.concurrency}")

        results = [None] * len(items)
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs = {pool.submit(_run_item, i, it, args, shot, style, key): i
                    for i, it in enumerate(items)}
            for fut in as_completed(futs):
                res = fut.result()
                results[futs[fut]] = res
                mark = "ok " if res["ok"] else "FAIL"
                print(f"  {mark} [{res['id']}] {res.get('file', res.get('error'))}")

        manifest = os.path.join(args.outdir, "manifest.json")
        json.dump({"shot": args.shot, "style": args.style, "preset": args.preset,
                   "aspect": _resolved_aspect(args, shot), "shared": args.shared,
                   "transparent": _wants_transparent(args, shot), "items": results},
                  open(manifest, "w"), indent=2, ensure_ascii=False)
        ok = sum(1 for r in results if r["ok"])
        print(f"done: {ok}/{len(items)} ok, manifest at {manifest}")
        return

    if not args.prompt or not args.out:
        sys.exit("Give either --prompt with --out, or --spec with --outdir.")
    written = _gen_one(args.prompt, args.rhythm_index, args.out, args, shot, style, key,
                       tag=os.path.splitext(os.path.basename(args.out))[0])
    print(f"ok {written}")


def cmd_cutout(args):
    """Pull alpha out of an image we did NOT generate. The delegated path ends here: higgsfield
    (or any other generator) makes the picture, this makes it transparent."""
    key = _api_key(args.key)
    shot, _ = resolve_axes(args.preset, args.shot, None)
    method = _matte_method(args, shot)
    tag = os.path.splitext(os.path.basename(args.out))[0]
    rgba = cutout_from(_read_image(args.image), key, method, args.debug_dir, tag,
                       args.bg_retries, args.anchor, not args.fill_width)
    out = save_rgba(rgba, args.out)
    print(f"ok {out}  ({rgba.size[0]}x{rgba.size[1]} RGBA, matte={method})")


def cmd_shots(args):
    for k, v in load_shots().items():
        if k.startswith("_"):
            continue
        hf = v.get("higgsfield") or {}
        route = hf.get("mode") or hf.get("model_hint") or "local only"
        print(f"{k:20} {v['label']:28} {v.get('default_aspect','1:1'):>5}  "
              f"transparent={v.get('transparent','no'):9} higgsfield={route}")


def cmd_styles(args):
    for k, v in load_styles().items():
        if k.startswith("_"):
            continue
        print(f"{k:20} {v['label']:22} [{v.get('register','')}]  palette: {v.get('palette','')}")


# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(
        description="Landing imagery: generate with Gemini, or pull a transparent cutout out of "
                    "any image (including one higgsfield produced).")
    sub = p.add_subparsers(dest="cmd", required=True)

    def matte_args(sp):
        sp.add_argument("--key", help="Gemini API key (else GEMINI_API_KEY env)")
        sp.add_argument("--matte-method", default=None, choices=["diff", "chroma", "white"],
                        dest="matte_method",
                        help="diff (A/B green difference), chroma (green only), white (single "
                             "white render, best for flat logos and icons). Default comes from "
                             "the --shot, else diff.")
        sp.add_argument("--anchor", default=None, choices=["bottom", "float"],
                        help="transparent layout: bottom = solid bottom edge with transparent "
                             "headroom and sides, so the subject stands on the section; float = "
                             "fully isolated floating cutout. `generate` defaults to bottom "
                             "because it composes the source that way; `cutout` defaults to "
                             "float because an arbitrary source is rarely bottom-composed.")
        sp.add_argument("--fill-width", action="store_true", dest="fill_width",
                        help="with --anchor bottom, the subject spans the full width so ONLY the "
                             "top is transparent (for wide subjects); default keeps L/R transparent")
        sp.add_argument("--debug-dir", default=None, dest="debug_dir",
                        help="save the raw renders (A natural, B green) here for matte tuning")
        sp.add_argument("--bg-retries", type=int, default=3, dest="bg_retries",
                        help="max attempts to get a keyable green background")

    def axis_args(sp):
        sp.add_argument("--shot", help="what the image depicts and how it is framed "
                                       "(see the `shots` command)")
        sp.add_argument("--style", help="how the image feels: palette, light, mood "
                                        "(see the `styles` command). One style per org.")
        sp.add_argument("--preset", help="deprecated single axis; resolves to a shot and style pair")

    g = sub.add_parser("generate", aliases=["single", "batch"],
                       help="one image (--prompt/--out) or a cohesive set (--spec/--outdir)")
    matte_args(g)
    axis_args(g)
    g.add_argument("--prompt", help="the subject to render (single image)")
    g.add_argument("--out", help="output path for a single image (.png/.jpg)")
    g.add_argument("--spec", help="jobs JSON for a set: {shared, items:[{id,subject}]}")
    g.add_argument("--outdir", help="output directory for a set")
    g.add_argument("--concurrency", type=int, default=3)
    g.add_argument("--rhythm-index", type=int, default=None, dest="rhythm_index",
                   help="pin a specific rhythm beat from the shot (single image)")
    g.add_argument("--style-ref", action="append", default=[], dest="style_ref", metavar="PATH",
                   help="image to use as a STYLE reference (repeatable); the set's whole look is "
                        "borrowed from these. Combines with or replaces a text --style.")
    g.add_argument("--shared", default="", help="shared CONTENT context injected into every prompt")
    g.add_argument("--aspect", default=None,
                   help="aspect ratio. Defaults to the --shot's natural ratio, else 1:1. The "
                        "prompt's composition clause follows this value.")
    g.add_argument("--extra", default="",
                   help="extra shot direction appended near the end of every prompt (lighting, "
                        "lens, camera, realism). A shot that needs a realism clause already "
                        "carries its own.")
    g.add_argument("--transparent", action="store_true", help="force an RGBA cutout")
    g.add_argument("--opaque", action="store_true",
                   help="force a normal image even for a shot that implies a cutout")
    g.set_defaults(func=cmd_generate, anchor_default="bottom")

    c = sub.add_parser("cutout", help="pull an RGBA cutout out of an existing image or URL")
    matte_args(c)
    c.add_argument("--image", required=True, help="local path or http(s) URL of the source image")
    c.add_argument("--out", required=True, help="output path (forced to .png)")
    c.add_argument("--shot", help="optional, only to inherit that shot's default matte method")
    c.add_argument("--preset", help="deprecated single axis")
    # An image we did not compose is almost never cropped by its bottom edge, and asking the
    # green pass to re-ground it makes the model recompose the subject instead of keying it.
    c.set_defaults(func=cmd_cutout, style=None, anchor_default="float")

    sub.add_parser("shots", help="list shots (what an image depicts)").set_defaults(func=cmd_shots)
    sub.add_parser("styles", help="list styles (how an image feels)").set_defaults(func=cmd_styles)
    sub.add_parser("presets", help="deprecated; lists styles").set_defaults(func=cmd_styles)

    args = p.parse_args()
    if getattr(args, "anchor", None) is None:
        args.anchor = getattr(args, "anchor_default", "bottom")
    global ASPECT
    if getattr(args, "aspect", None):
        ASPECT = args.aspect
    args.func(args)


if __name__ == "__main__":
    main()
