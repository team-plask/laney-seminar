# Art direction: choosing what an image looks like

Every image on a landing page is three independent choices. Keeping them independent is what
makes the system general: nine bundled presets could only make nine kinds of picture, while
three axes make every combination reachable, including the ones nobody thought to name.

## Contents

- [The three axes](#the-three-axes)
- [Style: one per org](#style-one-per-org)
- [Shot: pick by what the band has to say](#shot-pick-by-what-the-band-has-to-say)
- [The three hard cases](#the-three-hard-cases)
- [Visual rhythm](#visual-rhythm)
- [Cohesion inside a set](#cohesion-inside-a-set)
- [Style references](#style-references)
- [Before you ship a set](#before-you-ship-a-set)

## The three axes

```
image = surface x shot x style
```

| Axis | Question | Lives in | Decided by |
|---|---|---|---|
| **surface** | Where on the page does it land? | [`surfaces.md`](surfaces.md) | The section type and layout you chose in Phase 3 |
| **shot** | What does it depict, and how is it framed? | [`../scripts/shots.json`](../scripts/shots.json) | What the band has to say |
| **style** | How does it feel? | [`../scripts/styles.json`](../scripts/styles.json) | The brand, once, for the whole org |

Surface is mechanical, so read it off the table rather than deciding it. Shot changes band to
band. Style is fixed for the org. Run `python3 imagegen.py shots` and `styles` to see both
registries.

## Style: one per org

Pick one style, write it into the org's brief, and use it for every image on the page. A page
whose bands each have their own palette does not read as varied, it reads as unfinished.

**Then write the same palette into `organizations.theme`, or the page fights the pictures.**
The style axis colors the IMAGES. The page's own chrome, tone bands, buttons and links, comes
from `organizations.theme`, which is raw CSS custom properties parsed by `parseThemeCss` and
injected inline on the tenant subtree. Leave it empty and the platform default applies, which is
green. A clinic built entirely in `institutional-calm` navy came out with a **green closing CTA
band**, because the imagery was styled and the theme was never set. Nothing warns you: both
halves are individually correct.

Take the style's palette words and give them as a theme block. Setting these is enough:

```css
:root {
  --primary: oklch(0.355 0.065 252);            /* the tone-primary band and buttons */
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.928 0.014 252);          /* the tone-secondary band */
  --secondary-foreground: oklch(0.285 0.045 252);
  --muted: oklch(0.966 0.007 252);              /* the tone-muted band */
  --muted-foreground: oklch(0.515 0.025 252);
  --accent: oklch(0.928 0.014 252);
  --accent-foreground: oklch(0.285 0.045 252);
  --ring: oklch(0.355 0.065 252);
}
```

Check it after writing: the closing `tone: primary` band should be the brand color, not green.
A raw SQL update does not revalidate, so a cached page keeps the old theme until it re-renders.

Styles are grouped by register, which is usually how a customer describes what they want.

| Register | Styles | What the customer tends to say |
|---|---|---|
| Dignified | `editorial-warm`, `institutional-calm`, `luxe-dark` | 점잖은, 신뢰가 가는, 고급스러운 |
| Sophisticated | `clean-minimal`, `mono-editorial`, `tech-gradient` | 세련된, 깔끔한, 모던한 |
| Gentle | `soft-pastel`, `natural-organic`, `film-documentary` | 부드러운, 편안한, 자연스러운 |
| Loud | `bold-graphic` | 강렬한, 눈에 띄는 |
| Kitsch | `pop-maximal`, `retro-print`, `y2k-chrome`, `paper-collage` | 키치한, 발랄한, 재미있는 |
| Neutral | `flat-graphic` | Icons and logo marks only |

Three notes worth having before you choose.

**Register has to match the business, not the mood board.** A clinic that picks `pop-maximal`
because the founder likes it will read as unserious about medicine. When a customer asks for
something louder than their category supports, take the register one step out rather than
three: an `institutional-calm` clinic can move to `editorial-warm`, not to `y2k-chrome`.

**A kitsch style is a commitment.** `retro-print` and `paper-collage` are print and craft
media, so a photographic product cutout dropped into that page looks like a mistake. If you
choose one, every image on the page has to be made in it, including the logo.

**Bend a style rather than inventing one.** The `common` string's color words and mood words
are the levers. Copy the closest entry, change the palette to the brand's, keep the light and
medium words, and give it a new key.

## Shot: pick by what the band has to say

| The band is about | Shot |
|---|---|
| Where this happens, as a hero backdrop | `scene-wide` |
| A person, named or profiled | `portrait-headshot` |
| The work being done | `candid-at-work` |
| Using the thing | `hands-in-use` |
| The team | `group-team` |
| A machine, in full | `equipment-hero` |
| One part of a machine | `equipment-detail` |
| A product, for a catalog card | `product-catalog` |
| A product that must sit on a colored band | `product-cutout` |
| What the software does | `ui-screenshot` |
| A claim no screen can show | `metaphor-object` |
| Nothing in particular, filling a band | `abstract-form` |
| Material and craft, as a rest between sections | `detail-macro` |
| An illustrated tile | `icon-flat` |
| The brand mark | `logo-mark` |

A shot carries the constraints that shot always needs, so you do not have to remember them.
A people shot brings its own realism clause, which is the single biggest lever against waxy
AI skin. A cutout shot brings its matte method. Each brings its natural aspect ratio.

## The three hard cases

**People.** Ranked by how often the result is usable: `hands-in-use` is safest because there
is no face to get wrong, then `candid-at-work` where the face is small and turned away, then
`portrait-headshot`, and `group-team` is worst because every extra face multiplies the failure
rate. Reach for the safest shot that still makes the point. Describe a role and an age band,
never a real person's name. When the SAME face has to recur across several images, such as a
team grid, train a Soul once with `higgsfield-soul-id` and pass its reference id, rather than
hoping four separate renders agree.

**Value proposition.** Try `ui-screenshot` first. A real screen outperforms any metaphor on a
product landing, and it is the one image that proves the product exists. Fall back to
`metaphor-object` only for a claim no screen can show, and pick a concrete object rather than
the abstraction: a brass key in an open palm, not "security". Use `abstract-form` only as
decoration, and be honest that it carries no argument.

**Equipment.** Scale is what generated machinery gets wrong, so put a size cue in the subject
itself: waist height, on castors, beside a chair. `equipment-hero` keeps the room in frame
because the room is the size cue; `equipment-detail` drops it for one legible part. Both want
a concrete housing material, because "a laser device" invents a different machine every run.

## One model, recurring: the Korean clinic convention

A Korean dermatology or aesthetic clinic site is built around ONE model who appears on almost
every band, and the treatment cards show HER, not the machine. Equipment belongs on the
equipment page. A card headed 색소 shows a clear cheek, not a laser.

**Keep the same face across the set by passing the lead portrait as a reference.** Generate one
beauty portrait, then generate every other frame with `--image <that portrait>` and "same
person as the reference, same face and hair" in the prompt. Four separate portrait calls give
four different women, which reads as stock. One reference gives a model.

```bash
higgsfield generate create text2image_soul_v2 --prompt "<beauty portrait brief>" \
  --aspect_ratio 3:4 --wait                                    # the lead
higgsfield generate create nano_banana_2 --image lead.png \
  --prompt "Same woman as the reference, same face. <this frame>" --aspect_ratio 1:1 --wait
```

A set that works for a derm clinic: the lead portrait, a cheek close-up for pigment, an extreme
skin-texture macro for scarring, a jawline profile for lifting, and her pressing cream into her
cheek for aftercare. Describe an archetype and an age band, never a named person, and never ask
for a specific real individual's likeness.

**Name the treatments the way the clinic does, and give each one a page.** Korean clinics list
the devices they own by product name (울쎄라, 온다리프팅, 슈링크 유니버스, 인모드, 피코토닝,
포텐자, 리쥬란, 프락셀), not by abstract category, and each name is its own page with its own
hero. So the signature band's children ARE the treatment entities: a real `slug` on each makes
it a page at `/<slug>`, the nav dropdown points at the same nodes, and the card links there by
itself. Generated imagery is a stand-in and is not a photograph of any named device, so a live
tenant supplies its own photographs before publishing or drops the brand names.

Two things to check every time. **Studio equipment carries text**: a softbox edged into the lead
frame with a garbled brand on it, and cropping was faster than re-running. **Bare shoulders read
as skincare, clothing reads as clinical.** Pick one and hold it across the set.

## Visual rhythm

Rhythm is variation the eye reads as intentional. Three levers, and the style axis is not one
of them.

**Vary the shot down the page.** Alternate close and wide, and people and things. A run of
four card grids in a row reads flat no matter how good each image is.

**Vary the surface.** A full-bleed background, then cards, then a bottom-bleed cutout on a
color band, then a texture strip. The surface changes how an image meets the page, which is a
bigger perceptual change than the picture itself.

**Keep the style fixed.** This is what holds the page together while the other two vary.

**Reach past `grid`, and use `split`.** Both reference orgs on this platform, `laney` and
`lumiere-test`, set `split: true` on three bands each and pull from `zigzag`, `bento`,
`overlay`, `gallery`, `expandable`, `timeline`, `stats` and `marquee`. A page built from plain
card grids with the title always centred above is the flat result, however good the pictures
are. `zigzag` with a split title is the single biggest change available: the heading stays put
on the left while media and copy alternate sides down the section.

**Runs beat strict alternation.** Neither reference org flips tone every band. laney holds
`foreground` for three bands, lumiere holds `background` for three, then breaks. A run then a
break reads as intent; strict alternation reads as a rule being followed.

These sit alongside the `tone` and `align` alternation already described in the skill. A body
stack that works:

| Band | tone | align | shot | surface |
|---|---|---|---|---|
| Hero | background | center | `scene-wide` or `ui-screenshot` | `section-bg` or `hero-ui` |
| Features | secondary | start | `product-catalog` | `card-grid` |
| How it works | background | center | none, text accordion | none |
| Proof | foreground | start | `candid-at-work` | `card-grid` |
| Texture rest | background | center | `detail-macro` | `band-bleed` |
| Closing CTA | primary | center | `product-cutout` | `band-bleed` |

Two of the seven bands carry no image at all. That is deliberate: an image on every band is
the same failure as an eyebrow tag on every band.

## Cohesion inside a set

Within one set, meaning one batch of sibling cards, cohesion comes from three things being
shared: the style, the shot, and the `shared` context line. Variation comes from the shot's
`rhythm` list, which the batch cycles per item so the series gets a beat instead of looking
cloned.

Keep the subjects in a set parallel in scale and specificity. All single objects, or all the
same kind of scene. Mixing a bottle with a sunlit interior breaks a set no style can rescue.

For a stricter uniform grid, give the shot a single rhythm entry. For more variety, lengthen
the list. For one image you can pin a beat with `--rhythm-index`.

## Style references

`--style-ref` gives the style as images instead of words. Pass two to six images that clearly
agree on one aesthetic and the generator borrows their medium, grain, palette, light and mood
while rendering your subject. It combines with or replaces a text `--style`.

This is the most reliable way to match an established brand, so when an org has its own
photography, feed it as references and every generated image inherits it. A scattered mood
board averages into mush, so curate for one look. Mechanics and gotchas are in
[`imagegen.md`](imagegen.md).

## Before you ship a set

- No generated text anywhere except a real wordmark on the logo. Delegated prompts need the
  no-text clause appended explicitly; the cinematic models caption a scene otherwise.
- One style across every image on the page, including the logo.
- Every card in a card layout has a real image. A card with none is an empty box.
- The shot varies band to band, and at least one band carries no image.
- People images use the safest shot that still makes the point.
- A `ui-screenshot` has been read for garbled or misspelled words.
- Equipment has a size cue in frame.
- Cutouts are bottom-anchored unless they float inside a card.
