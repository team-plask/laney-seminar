# Surfaces: from a section to an image spec

A surface is where an image meets the page. It is the mechanical axis: once you have chosen a
section type and layout in Phase 3, the aspect ratio, the transparency and the anchoring
follow from that choice, so read them off this file rather than deciding them again per image.

Layout names here come from `features`, `faqs`, `logos`, `steps`, `stats` and `testimonials`
in [`packages/framework/src/sections.ts`](../../../packages/framework/src/sections.ts).
That file is the source of truth and the enums grow, so check it when a layout you want is
not listed.

## Contents

- [The surfaces](#the-surfaces)
- [Which features layout wants which surface](#which-features-layout-wants-which-surface)
- [Layouts that take no image](#layouts-that-take-no-image)
- [Where the image actually goes](#where-the-image-actually-goes)
- [Who generates it](#who-generates-it)
- [Wiring a batch back to rows](#wiring-a-batch-back-to-rows)

## The surfaces

| Surface | Comes from | Aspect | Transparent | Anchor | Shots that suit it |
|---|---|---|---|---|---|
| `section-bg` | any section with `background: true` | `16:9` | no | | `scene-wide`, `detail-macro` |
| `section-video` | same, but the URL ends in a video extension | `21:9` or `16:9` | no | | `scene-wide` |
| `hero-inset` | the hero, `inset: true`, with either of the two above | `21:9` or `16:9` | no | | `scene-wide` |
| `hero-ui` | `content`, `inset: true`, `background: false`, image on the hero entity | `21:9` | no | | `ui-screenshot` |
| `band-bleed` | `content` with a non-background image, below the heading | `21:9` | yes | bottom, `--fill-width` | `product-cutout`, `detail-macro`, `scene-wide` |
| `card-grid` | `features` card layouts, one image per child | `1:1` or `4:3` | no | | `product-catalog`, `candid-at-work`, `equipment-hero` |
| `card-cutout` | `features` `photo-card` on a colored band | `1:1` | yes | bottom | `product-cutout`, `portrait-headshot` |
| `card-float` | a card whose media floats inside its box | `1:1` | yes | float | `product-cutout`, `icon-flat` |
| `overlay-bleed` | `features` `overlay`, full-bleed image under a dark gradient | `4:3` or `16:9` | no | | `scene-wide`, `candid-at-work` |
| `screen-row` | `features` `screens`, or any layout with `framedMedia: true` | `16:9` | no | | `ui-screenshot` |
| `avatar` | `features` `team`, `testimonials`, chips | `1:1` | no | | `portrait-headshot` |
| `photo-frame` | `features` `timeline` or `collage`, framed polaroid photos | `4:3` | no | | `candid-at-work`, `group-team` |
| `logo` | `organizations.logo`, `logos` sections | `1:1` | yes, white matte | float | `logo-mark` |

**Match the ratio the renderer asks for, and make it EXACT.** Read the aspect class off the
layout before generating: `zigzag`'s media slot is `aspect-square md:aspect-4/5`
([features.tsx](../../../packages/landing-kit/src/render/components/sections/bodies/features.tsx)),
so it wants `4:5`, and a layout that declares no aspect inherits the shared card frame.

Asking the generator for a ratio is a request, not a contract. `--aspect_ratio 4:5` came back
`1856x2304`, which is 0.8056 rather than 0.800. Seven tenths of one percent is invisible in the
file and visible in the layout, as a pale band above and below the picture. The reference
tenant's hand-authored assets are exactly `1016x1270`, which is why their page looks right.
`imagegen.py` now centre-crops every result to the requested ratio, so use it, or crop whatever
a delegated call returns before writing the URL to a row.

Two rules that catch most mistakes.

**`band-bleed` must be wide AND transparent.** A content section's non-background image
renders as bottom-bleed media that melts into the tone band, so a square opaque image sits
there as an obvious pasted rectangle. `21:9`, background-free, tone showing through around it.

**Make it with the background remover, not the local green pass.** A `21:9` green pass is the
hardest case there is and it failed outright here: 3% transparent, effectively a rectangle. The
same subject through `image_background_remover` came back 71% transparent. Note that
`product-photoshoot` refuses `21:9` for some modes, so generate at `16:9` and crop.

**A "grounded" subject has to actually span the bottom.** `--fill-width` and the bottom anchor
only pay off when the subject really reaches across the frame at its lowest point. An
arrangement of separate objects has gaps down there, so cropping to its lowest opaque row buys
nothing and just makes the strip shorter. The reference tenant's CTA band is 94% opaque along
its bottom row; a row of vases and bottles is 1%. Either compose something continuous, or accept
that it floats on the band, which also reads fine.

**`card-cutout` is what makes `photo-card` work.** That layout deliberately puts no chrome
between the heading and the media, so a bottom-anchored transparent image fuses with its
heading into one unit. An opaque image there just reintroduces the box the layout removed.

**The hero is an inset panel.** `inset: true` gives it margin on all four sides, rounded corners,
and `overflow-hidden`, so the background is clipped by the rounding instead of running to the
viewport edges, and it takes a minimum height of the screen less those margins with its content
centred. A full-bleed hero is the fallback, not the default; both reference orgs inset theirs.

**A background can be a VIDEO, and it is the cheapest way to stop a hero looking static.** The
renderer checks the URL extension (`.mp4`, `.webm`, `.mov`, `.m4v`, `.ogv`) and plays a muted
looping video instead of an image, out of the SAME `entities.image` column, so there is no
schema change and no second field to fill. See
[`frame.tsx`](../../../packages/landing-kit/src/render/components/sections/frame.tsx).

Generate it with `higgsfield generate create seedance_2_0`, which takes `21:9`. Ask for ONE slow
move and nothing else: a dolly forward, a gentle pan, a single element drifting. A hero loops
behind a headline, so anything faster fights the copy. Keep people out of a looping background;
a repeating human gesture reads as a glitch.

**`team` and `collage` render their photos in grayscale.** The layouts desaturate, so palette
work is thrown away on those two surfaces. Judge a portrait or a polaroid frame on light, pose
and expression instead, and do not spend a re-run trying to get the brand color into one. Every
other surface keeps its color, which is why a page can look on-palette everywhere except the
team band and still be correct.

## Which features layout wants which surface

| `features.layout` | Surface | Notes |
|---|---|---|
| `grid`, `bento`, `slider`, `carousel`, `expandable`, `tabs`, `showcase` | `card-grid` | Every child needs a real image |
| `photo-card` | `card-cutout` | Heading fuses with the figure rising below it |
| `gallery` | `card-grid` | No card box, so soft and arty imagery can breathe |
| `overlay` | `overlay-bleed` | For dark bands only; text sits over the image |
| `screens` | `screen-row` | Tilted product-screen windows, so use real UI shots |
| `team` | `avatar` | Each child is a person with a name and role |
| `timeline`, `collage` | `photo-frame` | Framed photos, tilted; candid reads better than studio |
| `zigzag` | `card-grid` | Media and copy alternate sides down the section |
| `accordion`, `accordion-numbered` | none | Text rows, see below |

`framedMedia: true` wraps any card layout's media in browser chrome, which turns that section
into a screenshot section. Use it with `ui-screenshot` and not with photography.

## Bands that carry no image but carry the page

Two band types do more for rhythm than another card grid, and both need CONTENT written for them
first or they render empty. `laney` uses both.

**`stats`.** Four operating facts on a `foreground` band, placed right after a dark section so
the dark run continues rather than alternating. The field mapping is the opposite of what it
looks like: **`name` is the big metric and the localized `slogan` is the small caption under
it.** Putting the label in `name` renders "전문의 3인" huge and "3명" small, which reads as a
mistake. `animate: true` counts up from zero on scroll-in; it stalled at zero in local dev, so
verify it renders the real number and set `animate: false` if it does not.

**`marquee`. Always give its children images**, and pick the `variant` first, because the two
kinds are different bands rather than one band with a size knob. The renderer is
`c.image ? <Img …> : <span>{name}</span>`, so a child with no image silently falls back to its
name as text and the band becomes a scrolling word list, which reads as filler.

| `variant.kind` | Height | Fit | Content |
|---|---|---|---|
| `marks` (default) | `h-8 sm:h-10`, so 32 to 40px | `object-contain` | Flat wordmarks, partner logos, certification seals. `mono: true` greys them until hover |
| `gallery` | `sm` / `md` / `lg`, up to `h-80` at `md` | `object-contain`, or `object-cover` in a rounded tile with `boxed: true` | Equipment, product cutouts, anything worth seeing at size. The child's name rides underneath as a caption |

**Both variants want BACKGROUND-FREE subjects.** A marquee is a moving strip, and a subject
that floats on the band belongs to it, while a filled rectangle reads as a row of cards that
happens to slide. That is why `boxed` is off by default: turn it on only for photographs that
carry their own background and are meant to look like tiles.

**Use their `image_background_remover` for these, not the local green pass.** A residual halo
that is invisible on a white card is obvious on a marquee, because the band shows through
everything the matte left behind. This is the isolated-cutout case the delegation table already
points at, and skipping it put a grey cloud around every device on the strip.

**A photograph in `marks` is unreadable.** At 32px a floor-standing device is a grey sliver.
Either frame the subject horizontally so it survives the cap, or move it to `gallery`.

**Give `gallery` a heading.** The frame renders `SectionHeading` for a marquee like any other
band, so a large strip with an empty `slogan` shows a lone eyebrow over a row of pictures and
the reader has to guess what they are looking at. `marks` can stay bare; a trusted-by strip
explains itself.

Rows written before `variant` existed carry a top-level `mono`, which the schema lifts into
`{kind:"marks", mono}` so they render unchanged. Do not write `mono` at the top level in new
work.

## When a band reads flat

A band goes flat when the layout does the least a layout can do: a numbered row of four steps,
or a two-card grid. The content is fine; the component is the problem. The reference orgs reach
past the plain ones, and three replacements cover most cases.

- **A process or a list of promises** wants `accordion` or `accordion-numbered`. Compressed to
  one line each until opened, so four steps become four quiet rows instead of four blocks of
  prose, and the numbers keep the sequence. This is `lumiere-test`'s 약속 band. **It renders
  images**, one per row plus the open row's own, so give every child one; without them the band
  is text on a flat field, which is the same flatness you were escaping. The open row's image is
  large, so pick a frame that survives being the biggest thing on screen.
- **A journey with stages** wants `timeline` with `split: true`, which is the same org's 여정.
- **A set worth browsing** wants `carousel`. Set `bleed: true` and the track leaves the content
  column and runs edge to edge like a marquee: the first card still lines up with the heading,
  and the tail runs off the right so the next card peeks and the band invites a pull. `bleed`
  is off by default because seven tenants already run carousels inside the column.

**Check that the heading and the children still agree after a swap.** A band whose title is
about equipment and whose cards are about sunscreen reads as broken no matter which layout it
uses, and that mismatch is easy to carry along while changing components.

## Layouts that take no image

A card layout renders each child as a picture card, so a child with no image leaves an empty
box. When a section is a text-only value proposition, do not reach for a card layout and fill
it with icon glyphs. Use a layout that reads as rows instead.

- `features` `accordion` or `accordion-numbered` for feature lists and how-it-works
- `faqs` `accordion` for questions
- `steps` with a `connector` for a numbered process
- `stats` for numbers

An icon-only `grid`, meaning a card grid with `icon` set and no `image`, is the classic
mistake. Convert it to `accordion-numbered`, or commit and give every child a real image.

## Where the image actually goes

Images live on entities, never on sections. The section decides how the entity's image is
treated.

| Surface | The row that holds the URL |
|---|---|
| `section-bg` | the section's own entity `image`, with `background: true` |
| `hero-ui`, `band-bleed` | the section's own entity `image`, with `background: false` |
| every card surface | each CHILD entity's `image` |
| `avatar` | each child entity's `image` |
| `logo` | `organizations.logo`, or each logo child entity's `image` |

Because card surfaces read child images, the natural generation unit is one batch per section,
one item per child. That is also what gives the set its rhythm, since the batch cycles the
shot's beats by item order.

## Who generates it

Generation is delegated to the higgsfield skills. Transparency splits by **composition**, not
by capability: their `image_background_remover` returns a real RGBA PNG with better edges than
our green pass, but its only parameter is `medias`, so it cannot place a subject in the frame.
Anything that has to be cropped by the bottom edge with transparent headroom is composed here.

| Surface | Path |
|---|---|
| `section-bg`, `hero-ui`, `card-grid`, `overlay-bleed`, `screen-row`, `avatar`, `photo-frame` | higgsfield generates, save the result |
| `card-float` | higgsfield generates, then `image_background_remover` |
| `card-cutout`, `band-bleed` | higgsfield generates, then `imagegen.py cutout` grounds and keys it |
| `logo` | `imagegen.py generate --shot logo-mark`, single white render |

Each shot in [`../scripts/shots.json`](../scripts/shots.json) carries its own `higgsfield`
route, either a `higgsfield-product-photoshoot` mode or a `higgsfield-generate` model, plus a
`cutout` line saying which alpha route applies. A shot with `"higgsfield": null` stays local
because a single keyed render is cheaper and cleaner than a round trip.

**Model ids are not their names.** `nano_banana_2` is display-name "Nano Banana Pro", and "Nano
Banana 2" is the id `nano_banana_flash`. Every id in `shots.json` was read off `higgsfield model
list`. Check it again rather than trusting a name, in that file or anywhere else.

## Wiring a batch back to rows

A batch writes `manifest.json` next to the images, keyed by the `id` you gave each item. Use
the child entity's slug or name as that id and the mapping back to rows is already done.

Generated files are local. They become usable only once uploaded to the org's storage and the
resulting URL is written to `entities.image`. That upload depends on the org's Supabase
project and bucket, so confirm both for the target org before writing anything, as described
in [`data-model.md`](data-model.md).
