#!/usr/bin/env python3
"""
test_imagegen.py — guards for the parts of imagegen.py that failed silently.

No network and no API key: prompt assembly is pure string work, and the matte is tested on
synthetic A/B pairs, so this runs in CI in about a second.

    python3 test_imagegen.py

Each test names the failure it exists to prevent. All three were real.
"""
import importlib.util
import io
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ig", os.path.join(HERE, "imagegen.py"))
ig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ig)

FAILURES = []


def check(name, fn):
    try:
        fn()
        print(f"  ok    {name}")
    except AssertionError as e:
        FAILURES.append((name, str(e)))
        print(f"  FAIL  {name}\n        {e}")


# --------------------------------------------------------------------------- prompt assembly
def test_aspect_clause_follows_the_request():
    """The composition clause used to be hardcoded 'square 1:1' no matter what --aspect asked
    for, so a 21:9 band image was requested wide and described as square, and came back
    centered and cropped."""
    shot, style = ig.resolve_axes(shot="ui-screenshot", style="tech-gradient")
    wide = ig.compose("a dashboard", "", shot, style, 0, aspect="21:9")
    # Match the composition clause itself. A shot's framing may legitimately contain the word
    # "square" ("the screen square-on"), which is about the camera, not the frame.
    assert "21:9" in wide, f"wide prompt lost its ratio: {wide[-120:]}"
    assert "square 1:1 composition" not in wide, f"wide prompt still says square: {wide[-120:]}"

    shot, style = ig.resolve_axes(shot="product-catalog", style="clean-minimal")
    sq = ig.compose("a bottle", "", shot, style, 0, aspect=None)
    assert "square 1:1" in sq, f"square prompt lost its clause: {sq[-120:]}"


def test_shot_supplies_its_own_aspect():
    """A composer called without an explicit aspect must fall back to the SHOT's natural ratio,
    not the module default, or a wide shot silently describes itself as square."""
    for name, want in [("scene-wide", "16:9"), ("equipment-hero", "4:3"), ("ui-screenshot", "21:9")]:
        shot, style = ig.resolve_axes(shot=name, style="clean-minimal")
        for composer in (
            lambda: ig.compose("a thing", "", shot, style, 0, aspect=None),
            lambda: ig.compose_isolated("a thing", "", shot, style, "", None),
            lambda: ig.compose_grounded("a thing", "", shot, style, "", False, None),
        ):
            assert want in composer(), f"{name} did not carry {want}"


def test_people_shots_carry_the_realism_clause():
    """Realistic skin is the biggest lever against waxy AI faces. It used to be a manual
    --extra the caller had to remember, so it was usually missing."""
    for name in ["portrait-headshot", "candid-at-work", "hands-in-use", "group-team"]:
        shot, style = ig.resolve_axes(shot=name, style="luxe-dark")
        assert "skin texture" in ig.compose("a person", "", shot, style, 0), f"{name} lost realism"


def test_old_preset_names_still_resolve():
    """--preset was the single axis before the split. Existing commands must keep working."""
    expected = {
        "clean-studio": ("product-catalog", "clean-minimal"),
        "portrait": ("portrait-headshot", "clean-minimal"),
        "flat-icon": ("icon-flat", "flat-graphic"),
    }
    # resolve_axes re-reads the registries, so compare by value, not identity.
    shots, styles = ig.load_shots(), ig.load_styles()
    for old, (want_shot, want_style) in expected.items():
        shot, style = ig.resolve_axes(preset=old)
        assert shot == shots[want_shot], f"{old} lost its shot"
        assert style == styles[want_style], f"{old} lost its style"
    for old in ["editorial-warm", "luxe-dark", "soft-pastel", "natural-organic",
                "bold-graphic", "tech-gradient"]:
        _, style = ig.resolve_axes(preset=old)
        assert style == styles[old], f"{old} no longer resolves to a style"


def test_registries_agree():
    """A shot pointing at a style that does not exist, or an alias at a missing shot."""
    shots, styles = ig.load_shots(), ig.load_styles()
    known = set(ig.public_keys(styles))
    for name in ig.public_keys(shots):
        shot = shots[name]
        assert shot.get("framing"), f"shot {name} has no framing"
        hint = shot.get("style_hint")
        assert not hint or hint in known, f"shot {name} hints at unknown style {hint}"
    for name, alias in styles.get("_aliases", {}).items():
        if name.startswith("_"):
            continue
        assert alias.get("style", next(iter(known))) in known, f"alias {name} has an unknown style"
        assert alias.get("shot", name) in shots or "shot" not in alias, f"alias {name} unknown shot"


# --------------------------------------------------------------------------- matte
KEY = (0, 177, 64)


def _jpg(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8"), "RGB").save(buf, "JPEG", quality=98)
    return buf.getvalue()


def _pair(bg_a, n=512):
    """A synthetic A/B pair: the same subject on `bg_a` and on the chroma key. The subject has
    a red half and a genuinely LIME half, which is the case the difference matte exists for."""
    def canvas(bg):
        c = np.zeros((n, n, 3), float)
        c[:, :] = bg
        c[160:360, 120:250] = (200, 60, 50)    # red
        c[160:360, 262:392] = (140, 190, 60)   # lime: green, but part of the subject
        return c
    return _jpg(canvas(bg_a)), _jpg(canvas(KEY))


def _regions(rgba):
    a = np.asarray(rgba)[..., 3].astype(float) / 255
    return a[200:320, 150:220].mean(), a[200:320, 295:360].mean(), a[20:120, 20:120].mean()


def test_key_background_dies_at_every_source_brightness():
    """A grey in A whose brightness sits near the key's own distance-minimum made |A-B| dip
    below the threshold, so a ghost of the backdrop matted through at about 15% alpha. It
    attached to the subject through partial alpha, so no component filter could drop it. Seen
    for real on a luxe-dark spotlight gradient."""
    for label, bg in [("mid grey", (77, 77, 77)), ("dark", (20, 20, 24)),
                      ("light", (225, 225, 228)), ("near-key luminance", (60, 110, 75))]:
        red, lime, back = _regions(ig.matte(*_pair(bg), method="diff"))
        assert back < 0.03, f"{label}: background survived at alpha {back:.2f}"
        assert red > 0.95, f"{label}: subject was eaten"


def test_green_subject_is_rescued():
    """The whole reason the difference term exists: a genuinely green part of the SUBJECT agrees
    across the pair, while real background does not. Killing the ghost must not kill this."""
    for bg in [(77, 77, 77), (20, 20, 24), (225, 225, 228)]:
        _, lime, _ = _regions(ig.matte(*_pair(bg), method="diff"))
        assert lime > 0.90, f"lime subject was keyed away at alpha {lime:.2f}"


def test_nearest_aspect_round_trips():
    """`cutout` infers the green pass ratio from the source, so a wide input stays wide."""
    for w, h, want in [(2048, 2048, "1:1"), (2560, 1097, "21:9"), (1024, 1820, "9:16"),
                       (2048, 1152, "16:9"), (1600, 1200, "4:3")]:
        got = ig._nearest_aspect(w, h)
        assert got == want, f"{w}x{h} inferred {got}, expected {want}"


# --------------------------------------------------------------------------- run
if __name__ == "__main__":
    print("prompt assembly")
    check("aspect clause follows the requested ratio", test_aspect_clause_follows_the_request)
    check("a shot supplies its own aspect", test_shot_supplies_its_own_aspect)
    check("people shots carry the realism clause", test_people_shots_carry_the_realism_clause)
    check("old --preset names still resolve", test_old_preset_names_still_resolve)
    check("shots and styles agree", test_registries_agree)
    print("matte")
    check("key background dies at every source brightness", test_key_background_dies_at_every_source_brightness)
    check("a green subject is rescued", test_green_subject_is_rescued)
    check("nearest aspect round-trips", test_nearest_aspect_round_trips)

    if FAILURES:
        print(f"\n{len(FAILURES)} failed")
        sys.exit(1)
    print("\nall passed")
