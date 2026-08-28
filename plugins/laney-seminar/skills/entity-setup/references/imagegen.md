# `imagegen.py`: the local generator and the cutout

Generation is normally delegated to the higgsfield skills. This script covers what does not
delegate: **grounded cutouts**, **flat-art mattes**, and a **direct Gemini path** for when their
auth is unavailable.

For an ISOLATED cutout, use their `image_background_remover` instead. It returns a real RGBA
PNG, its edges on glass and hair beat the green pass here, and it costs one call rather than
three. What it cannot do is place the subject: its only parameter is `medias`. A band image has
to be cropped by the bottom edge with transparent headroom above it, and that composition comes
from the grounded prompt below, so `--anchor bottom` and `--fill-width` stay local.

Which look to choose is [`art-direction.md`](art-direction.md). Where an image lands and what
spec that implies is [`surfaces.md`](surfaces.md). This file is the mechanics.

## Contents

- [Commands](#commands)
- [How a prompt is assembled](#how-a-prompt-is-assembled)
- [Writing subjects](#writing-subjects)
- [Style references](#style-references)
- [Extra shot direction](#extra-shot-direction)
- [Cutouts](#cutouts)
- [Transparency gotchas](#transparency-gotchas)
- [Aspect ratios](#aspect-ratios)

## Commands

```bash
export $(grep -v '^#' ../.env.local | xargs)   # GEMINI_API_KEY, never committed
cd scripts

python3 imagegen.py shots      # what an image depicts
python3 imagegen.py styles     # how an image feels

# one image
python3 imagegen.py generate --shot scene-wide --style editorial-warm \
  --prompt "a sunlit specialty-coffee bar counter just after opening" --out out/hero.jpg

# a cohesive set, one image per child entity
python3 imagegen.py generate --spec jobs.json --shot product-catalog \
  --style clean-minimal --outdir out/menu/

# alpha out of an image we did not generate
python3 imagegen.py cutout --image https://.../higgsfield-result.png --out out/serum.png
python3 imagegen.py cutout --image logo.png --matte-method white --out out/logo.png
```

`single` and `batch` still work as aliases of `generate`, and `--preset` still resolves to a
shot and style pair, so older commands keep running. Prefer `--shot` and `--style` in new work.

Needs Python with `numpy` and `pillow`. `scipy` is optional and only improves matte cleanup.

The spec for a set:

```jsonc
{
  "shared": "product hero shots for a minimalist Korean skincare line",
  "items": [
    { "id": "cleanser", "subject": "a white tube of gentle facial cleanser" },
    { "id": "toner",    "subject": "a clear glass bottle of hydrating toner" }
  ]
}
```

Give each item the child entity's slug as its `id` so `manifest.json` maps straight back to
the row you have to update.

## How a prompt is assembled

```
subject . shared . shot.framing . shot.rhythm[i] . style.common . shot.extra + --extra . framing clause
```

- **subject**, you write it, material first.
- **shared**, one line of context for the whole set.
- **shot.framing** and **shot.rhythm[i]**, composition and the per-item beat, from the shot.
- **style.common**, palette, light, medium and mood, from the style.
- **shot.extra**, the quality lever that shot always needs. A people shot carries its own
  realism clause so you do not have to remember it.
- **framing clause**, generated from the aspect ratio actually being requested.

For a transparent render the natural pass instead uses an isolation prompt, a single object
with no props, and keeps only the style's palette. A style's full `common` can build a whole
lit scene, and a scene cannot be keyed.

The aspect resolves as explicit `--aspect`, then the shot's `default_aspect`, then `1:1`, and
the prompt's composition clause follows whatever wins. Do not hand-write "wide" or "square"
into a subject; it will contradict the clause.

## Writing subjects

Name form, material, color, and the one defining detail. Leave style to the style axis.

- Good: `a matte black hand coffee grinder with a wooden knob`
- Good: `a round frosted-glass jar of moisturizing cream, minimal label`
- Weak: `grinder`, `face cream`. The model invents everything and a set drifts apart.

Keep subjects in a set parallel in scale and specificity. Consistent branding emerges on its
own, since the model invents a plausible brand and carries it across the batch. For a specific
name, quote it: `a coffee bag labelled "OARO"`.

Each shot's `subject_hint` says what that shot needs from a subject. Read it before writing.

## Style references

`--style-ref <path>`, repeatable, gives the style as images. The references lead the prompt and
a directive tells the model to match their medium, grain, palette, light and mood while
rendering your subject rather than copying their content.

- Two to six images that clearly agree on one aesthetic. A scattered mood board averages into
  mush.
- Subjects should differ from the references. That is how you know style transferred and not
  content.
- A batch shares the references across every item, which is the strongest cohesion available,
  stronger than a text style alone.
- Best use here: feed a tenant's OWN existing photography so generated images match their
  established identity exactly.

The model tends to clean up grainy or abstract reference styles, rendering them crisper than
the references are. The directive pushes back by demanding soft, painterly forms with the
grain rendered into the image itself. If a run still comes back too clean, reinforce `--shared`
with words like `soft-focus, hazy, heavily grainy, abstract, low-detail, risograph`. The grain
is the model's own; the script adds no post-process noise. The directive also forbids text, so
incidental captions and watermarks in the references do not propagate.

## Extra shot direction

`--shared` carries content context; `--extra` carries shot direction, the lighting, lens,
camera and realism qualifiers that push a render from plasticky toward photographic. Reach for
it when a result looks waxy or CGI-clean and the shot has no realism clause of its own.

- Light: `natural lighting`, `soft window light`, `cinematic lighting`, `golden hour`
- Lens: `shot on a Sony A7 with an 85mm lens`, `shallow depth of field`, `35mm film`
- Realism: `photorealistic`, `realistic skin texture with visible pores`, `subtle natural
  imperfections`, `not plastic, not airbrushed`

Do not add a realism clause to `y2k-chrome` or `paper-collage`. Those styles are artificial by
design and the two instructions fight.

## Cutouts

`cutout` takes an image and returns RGBA. It does not care who made the image, which is what
makes delegation work: higgsfield renders, this pulls the alpha.

The green method renders the subject onto a chroma-key green background with your image handed
back as a reference, then recovers alpha from the known key color. The difference between the
two frames rescues genuinely green parts of the subject, because those agree across the pair
while real background does not. The green pass is requested at the source image's own ratio,
so a wide input stays wide.

The white method needs no second render. Flat art is ink on a light ground, so distance from
white IS the alpha. It is cheaper, and it sidesteps the model's habit of standing a logo on a
reflective pedestal.

Match the method to the material. Green for photographic objects such as glass, metal, food and
packaging. White for flat art such as logos, icons and flat illustrations. Green on a flat logo
invites a keyable-looking pedestal; white on a glossy product leaves its highlights half
transparent. A shot that implies a cutout already carries the right default.

**Anchoring.** A green cutout is bottom-anchored by default: the subject sits at the bottom
edge with transparent headroom and sides, so it stands on a section rather than floating.

- `--anchor bottom`, the default. Right for people, products and most band media.
- `--anchor float`, all four sides transparent. For a chip thumbnail or media floating inside
  a card.
- `--fill-width`, with `bottom`, for a subject that spans the frame width such as a wide scene.
  Do not use it for a narrow subject; the sides would have nothing to fill and would key
  messily.

The white method is always isolated and ignores anchoring.

## Transparency gotchas

- **One subject only.** A flat-lay of five things will not key. That is five cutouts.
- **Grounded framing is a crop, not a floor.** The prompts frame the subject as cropped by the
  bottom edge with flat green everywhere else. Saying "standing on a floor" makes the model
  paint a graduated backdrop that keys into a haze band.
- **Ghost or double subject on large faces.** The green pass occasionally leaves a misaligned
  copy floating in the headroom. Two defenses are on by default: the prompt demands exactly one
  subject with no duplicate or mirror, and a grounded matte keeps only alpha connected to the
  bottom edge, since the real subject grounds there and a floating ghost does not. If one still
  slips through, re-run it.
- **Green-ish subjects** are handled by the difference term. Very saturated pure-green subjects
  are the worst case; keep the default `diff` method rather than `chroma` and check the result.
- **Soft or translucent edges** such as glass, steam and hair come through as partial alpha,
  usually well. Spill suppression already pulls green down at the edges.
- **Shadows.** The prompts forbid ground shadows. A faint bottom band occasionally leaks
  through; that is render variance, so re-run.
- **Debugging.** `--debug-dir <dir>` saves the raw renders, `<id>_A.jpg` natural and
  `<id>_B.jpg` green, so a matte can be re-tuned offline. A weak-green warning means the model
  would not isolate the subject: simplify it or re-run.

## Aspect ratios

Supported: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`, `1:4`,
`4:1`, `1:8`, `8:1`. Every image is 2K.

`21:9` is the widest useful ratio and is what below-heading band media wants. A square image
in that position is far too tall. `cutout` infers its green pass ratio from the source image,
so a wide input round-trips correctly.
