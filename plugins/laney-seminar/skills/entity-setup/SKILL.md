---
name: entity-setup
description: >-
  Populate an organization's landing-page content in this framework, its `entities`
  (the content graph), `products`, and `sections`, from a data source: generate cohesive
  2K imagery, write the entity copy, and compose the sections into a beautiful landing
  page. Use this WHENEVER the task is to fill in / seed / set up / bootstrap an org's
  content, build or populate a landing page, generate a set of entity or product images,
  create transparent product cutouts, or turn a catalog / brand brief / data dump into
  entities, products, and sections. Trigger even when the user only names part of it
  ("generate images for these products", "write the hero copy", "lay out the sections",
  "인물 사진 뽑아줘", "장비 사진", "키치한 느낌으로"). Those are steps of this workflow.
  When a prospect/stub's source facts are still scattered, conflicting, or unlicensed,
  use `org-launch-prep` first and return here with its approved ontology handoff.
  NOT for a bespoke enterprise landing in its own repo or a design that section options
  cannot express (that is `custom-landing`).
---

# Entity Setup

Turn a data source (a catalog, a brand brief, a spreadsheet, a scrape) into a finished
landing page for one org, in three phases:

An approved `org-evidence` / `org-launch-prep` ontology handoff is a prepared data source.
This skill consumes that handoff; it does not repeat its public-source collection or
conflict and rights adjudication.

1. **Imagery**, generate the pictures the page needs.
2. **Entity copy**, write the content graph (`entities`) wired to those images.
3. **Section composition**, arrange `sections` into a page with rhythm, tone, and CTAs.

The three build on each other but are independently useful. A user may ask only for a batch
of images, or only for the section layout.

**Seminar / owner self-service path.** When the org's own owner is present and is the
authority on their own facts (a doctor setting up their own clinic at a live session), the
`org-launch-prep` approval gate collapses to that person, and the write path is the laney
MCP rather than SQL. In that mode this skill consumes an `org-scrape` corpus directly and
writes only what the MCP boundary allows — entities, products, promotions, and the org base
prompt — leaving imagery and sections for the dashboard. The full contract is
[`references/seminar-mcp-path.md`](references/seminar-mcp-path.md).

## Uses

| Dependency | Read it for |
|---|---|
| [`laney-writing/references/writing-principles.md`](../laney-writing/references/writing-principles.md) | Universal clarity and evidence rules. Phases 2 and 3 |
| [`laney-writing/references/customer-voice.md`](../laney-writing/references/customer-voice.md) | Customer-facing voice. Phases 2 and 3 |
| [`references/data-model.md`](references/data-model.md) | The `entities` / `products` / `sections` contract. Read before writing any row |
| [`references/art-direction.md`](references/art-direction.md) | Which shot and which style, and how rhythm works |
| [`references/surfaces.md`](references/surfaces.md) | Section and layout mapped to an image spec |
| [`references/imagegen.md`](references/imagegen.md) | The local generator and the cutout, in detail |
| `higgsfield-product-photoshoot` skill | Product and people photography |
| `higgsfield-generate` skill | Scenes, product screens, model routing |
| `higgsfield-soul-id` skill | Holding one face steady across a set |

External skills are declared in `skill-package.json` and locked by
`skillpm-lock.json`.

---

## Phase 1: Imagery

**Three independent choices make every image**, and keeping them independent is what lets this
cover any case and any style:

| Axis | Question | Decided by |
|---|---|---|
| **surface** | Where on the page does it land? | The section and layout, read off [`surfaces.md`](references/surfaces.md) |
| **shot** | What does it depict, how is it framed? | What the band has to say. `python3 scripts/imagegen.py shots` |
| **style** | How does it feel? | The brand, ONCE, for the whole org. `python3 scripts/imagegen.py styles` |

Read [`art-direction.md`](references/art-direction.md) before choosing. It carries the style
registers (dignified, sophisticated, gentle, loud, kitsch), the rules for the three hard cases
(people, value proposition, equipment), and the rhythm rules.

### Who generates

**Generation is delegated to the higgsfield skills.** They maintain the model catalog and the
photography vocabulary, and that is not work worth duplicating here.

| Need | Path |
|---|---|
| A product or a person, in a scene or on a card | `higgsfield-product-photoshoot`, with the mode from the shot |
| A place, a product screen, an abstract form | `higgsfield-generate`, with the model from the shot |
| The same face across several images | `higgsfield-soul-id` once, then pass its reference id |
| An ISOLATED cutout (floating, all sides transparent) | `higgsfield-generate` model `image_background_remover` |
| A GROUNDED cutout (bottom-anchored, or `--fill-width`) | generate first, then `imagegen.py cutout` |
| A logo or a flat icon | `imagegen.py generate`, single white render |
| higgsfield auth unavailable | `imagegen.py generate` and `cutout`, direct Gemini |

**Both alpha routes are real, and the split is about composition, not capability.**
`image_background_remover` returns a genuine RGBA PNG and its edges on glass and hair are better
than our green pass, for one call instead of three. But its only parameter is `medias`, so it
cannot place a subject: a band image has to be cropped by the bottom edge with transparent
headroom, and that composition comes from our grounded prompt. So isolated goes to them,
grounded stays here, and flat logos stay here because a single white render is cheaper than a
round trip.

**Read the live catalog, not a name.** Every model id in
[`scripts/shots.json`](scripts/shots.json) was read off `higgsfield model list`, because the ids
do not mean what they say: `nano_banana_2` is display-name "Nano Banana Pro", while "Nano Banana
2" is the id `nano_banana_flash`. Their own docs get this wrong. Re-check with `higgsfield model
list` before trusting any id, including the ones in our file.

**Check auth before planning a batch.** `higgsfield account status` failing with
`Session expired` means a human has to run `hf auth login`. It is interactive, so an agent
cannot do it. Say so early rather than halfway through a set.

### The delegated path

**Send a SHORT intent, not a composed prompt.** `higgsfield-product-photoshoot` says it plainly:
the backend assembles the final prompt, never write one freehand. `--prompt` is user intent,
one line. Their enhancer turns it into a sectioned brief with `[SCENE]`, `[HUMAN ELEMENT]`,
`[LIGHTING]` (source angle, size, colour temperature, fill, falloff), `[LENS & CAMERA]` (focal
length and aperture), `[STYLE REFERENCE]` naming real photographers, and a 40-line `[AVOID]`
block. Pushing our own long prompt in fights that and produces exactly the flat, generic result
it is built to prevent. Their own guidance says the same thing from the other side: keep prompts
under about 200 tokens, models distort on long ones.

```bash
higgsfield product-photoshoot create --mode lifestyle_scene \
  --prompt "a Korean dermatologist reviewing a skin analysis with a patient" \
  --brand_context "Yeonseo Dermatology, Gangnam. Restrained, navy and cool white, quietly premium." \
  --aspect_ratio 4:3
```

- `--prompt` is the intent. Name the market and the subject, nothing else.
- `--brand_context` carries the org and the palette. This is where the style axis goes, NOT
  glued onto the prompt.
- `--product_context` adds detail about the object when there is one.
- `--enhance-only` returns the assembled prompt WITHOUT generating. Free, fast, and the best way
  to see what the mode will actually do before spending on a batch. Read it once per new mode.

For `higgsfield-generate` there is no enhancer, so there you do write the prompt: subject,
setting, camera (lens, angle, motion), lighting, medium, in that order and still short.

**Keep text out, but say it POSITIVELY where you can.** Most of these models expose no
`negative_prompt`, and their own guidance is to phrase positively: "tack sharp" beats "no blur".
A wall of `no X` competes with the subject for the token budget and only half works, which is
what we measured. So lead with the positive form and keep a short negative tail:

```
clean unmarked walls, blank surfaces, plain undecorated panels.
no text, no lettering, no signage, no logos
```

Add `plain unmarked coat, no embroidery` when people are in frame. On the delegated
`product-photoshoot` path you can drop this entirely: their `[AVOID]` block already carries
"no warped or smeared text, no fake words baked into the image, no random unrelated brand
logos, no watermarks", and it is applied after the enhancer, where it works.

**The clause helps and does not settle it, so look at every delegated image before you use
it.** The cinematic models read a prompt as a film scene WITH A SUBTITLE. Unguarded,
`soul_location` burned "Thee Specialty-coffee l-tiust after opening" across a hero. Guarded,
one run came back clean and the next captioned a clinic lounge with "The trusting handshacipe
was over. Google Welcome to pay per appointment?". Roughly half. `text2image_soul_v2`
embroidered garbled Korean onto two of three white coats. Re-run anything with text in it.

For a **hero backdrop**, where a headline sits on top and a caption is fatal, prefer the local
Gemini path: its style directive forbids text and has not leaked.

**Name the market in people subjects.** "a Korean woman dermatologist in her forties in a white
coat", not "a dermatologist". Left unsaid, these models default to Western faces, which reads
wrong on a Korean clinic page.

**Pass the org's palette to flat art.** `icon-flat` and `logo-mark` use the `flat-graphic`
style, which carries no brand colors, so put them in `--shared` ("in deep navy and cool white
only"). Skipping this on a navy clinic returned teal, red and green icons and a green logo
while every photographic image on the page was correctly on-palette.

**Signage is a separate leak from captions.** The no-text clause stops a burned-in subtitle. It
does not stop the model inventing a brand and lettering it onto a wall: a clinic hero made on
the LOCAL path, whose directive forbids text outright, came back with "AESTHETICA DERMATOLOGY"
on the lobby wall. Any shot that depicts a place will do this. Read the walls, the reception
desk and the equipment panels, and re-run or crop when a name that is not the org's is legible.

**`team` and `collage` desaturate.** Those two layouts render their photos in grayscale, so
palette work is discarded there. Do not spend a re-run getting brand color into a team portrait.

### The local path

```bash
export $(grep -v '^#' skills/entity-setup/.env.local | xargs)
cd skills/entity-setup/scripts

python3 imagegen.py shots        # what an image depicts
python3 imagegen.py styles       # how an image feels

# one image
python3 imagegen.py generate --shot scene-wide --style editorial-warm \
  --prompt "a sunlit specialty-coffee bar counter just after opening" --out out/hero.jpg

# a cohesive set, one image per child entity
python3 imagegen.py generate --spec jobs.json --shot product-catalog \
  --style clean-minimal --outdir out/menu/

# alpha, on an image from anywhere
python3 imagegen.py cutout --image https://.../result.png --out out/serum.png
```

A **set** is the core unit: one image per child of an entity, sharing a style and a shot,
cycling the shot's rhythm beats by item order so the series has a tempo instead of looking
cloned. Give each item the child's slug as its `id` and `manifest.json` maps straight back to
the rows. Every image is 2K, and the aspect ratio follows the shot unless you override it.

`single`, `batch` and `--preset` still work as aliases, so older commands keep running.

### Choosing well

- **Write concrete subjects.** "an amber glass serum dropper bottle with a bamboo cap" beats
  "serum". Name material, form and color; let the style carry light and mood. Each shot's
  `subject_hint` says what that shot needs.
- **One style for the whole org.** Rhythm comes from varying the shot and the surface. A page
  where every band has its own palette reads as unfinished, not as varied.
- **A cutout is one object.** Do not ask for a transparent "flat-lay of five things"; that is
  five cutouts.
- **Tune, then commit.** For a big set, make one or two items first, look at them, adjust, then
  run the rest. A full page is not cheap: 19 images covering every shot, plus the re-runs the
  checks below forced, came to about 72 higgsfield credits and roughly 12 minutes at five in
  parallel.
- **Look at every image before you use it.** Text leaks, Western faces on a Korean page, and
  flat art in the wrong palette all pass silently and all showed up in one real run.
- **Look at what came back.** A `ui-screenshot` often renders panel titles as real words and
  sometimes misspells one. Read the words before shipping it.

Deeper prompt craft, transparency gotchas and matte debugging are in
[`imagegen.md`](references/imagegen.md).

### Wiring images to content

Generated files are local. To become an `entities.image` or a section background they must be
uploaded to the org's storage and the URL written to the row. That upload depends on the org's
Supabase project and bucket, so confirm both for the target org before writing. Key the work by
the batch `manifest.json`, whose `id` is the entity or product the image belongs to.

---

## Phase 2: Entity copy

Write the `entities` graph for the org from the data source: root nodes (hero, each feature
group, the faq group, footer groups) and their children, each with `name` / `label` /
`slogan` / `description` (localized), an `icon` (a hugeicons name), a `slug` where it should be
its own page, and the `image` from Phase 1. Parent and child are linked by `entity_edges` rows,
not by a column. See [`data-model.md`](references/data-model.md) for field roles and the graph
shape.

**문체는 [`laney-writing/references/customer-voice.md`](../laney-writing/references/customer-voice.md) 를 따른다**. 엔티티 카피는
방문자가 읽는 고객 대면 텍스트다. 금지 문자뿐 아니라 **「문장 만들기」 절 전체**가 적용된다:
명사구 토막 문장 금지, 평소 쓰는 단어로, 번역체 명사형 대신 동사. 슬로건은 짧아야 하지만
**짧은 것과 토막난 것은 다르다.** 아래 규칙은 그 위에 얹히는 **레이아웃 제약**이다.

**Voice, write titles as slogans, not labels.** The `slogan` becomes a section's *heading*, so
it must read like a headline with a point of view, not a dry category name. "전문 의료진"
(Professional staff) is a label; "당신의 얼굴을 가장 오래 들여다본 사람들" (The people who've
studied your face the longest) is a slogan. Do this for every heading, sections AND cards.

**Keep it to the line budget, long copy breaks the layout.** These are hard limits, not
suggestions (they wrap and overflow otherwise):

- **`slogan` (heading): 2 rendered lines at most.** A hero headline is about 6 to 8 Korean words
  or 5 English words per line; if it would spill to 3 lines, cut it. "시술 하나를 등록하면,
  검색되는 페이지가 하나 생깁니다" is 3 lines, tighten to "등록하면, 검색되는 페이지가 됩니다".
- **`description` (body): 1 to 2 sentences, 2 lines at most.** One specific idea, what it does
  or the promise, not a paragraph. A hero that fills 4 lines is too long, halve it.

Write BOTH `ko` and `en` and check both stay within budget. English usually runs longer.

**The budget is for copy that renders unconditionally.** An answer inside a `faqs` accordion is
hidden until someone opens it, so it may run to 3 or 4 sentences when the question needs them.
It still follows the voice rules, and it still should not become a paragraph. Everything that
renders without a click, every heading and every section body, holds to the two lines above.

**`name` is the eyebrow chip, one concept, never a stat combo.** `name` renders as the small tag
above the heading. Keep it a single plain concept ("AI 응대", "고객 이야기"). NEVER pack two
pieces of information into it with a separator. `"NO-SHOWS · −27%"`, `"SETUP, ONE DAY"` and
`"PAGES, AUTO-BUILT"` are all wrong, because a label plus a metric is two pieces of information.
Put the metric in the slogan or a `stats` section and keep the eyebrow to the label alone
("예약 엔진", "도입").

**Don't tag every section.** Eyebrows are seasoning, 4 or 5 across a page, not one per band. On
sections where the slogan already carries the point (benefit bands, stats, steps), suppress the
eyebrow with the section option `fields: {tag: "none"}` rather than inventing a chip for each.

**Every card needs an image, or it isn't a card.** A card layout renders each child as a picture
card, so a child with no `image` leaves an ugly empty box. Either give EVERY child in that
section a real image (one Phase 1 set, one item per child), OR, for text-only value props, use a
layout that reads as rows: `accordion` or `accordion-numbered` for features, an accordion for
`faqs`, `steps` for a process, `stats` for numbers. An icon-only grid, meaning a card `grid`
with `icon` and no `image`, is the classic mistake. Which layouts need images is the table in
[`surfaces.md`](references/surfaces.md).

---

## Phase 3: Section composition

Compose `sections` into the page: a `header`, a hero (`content` + `background` + `size: lg`),
feature / faq / testimonial bands, a photo-card or carousel section, and a closing CTA band,
each referencing an entity root and carrying a `tone`, an `align`, and optional `cta`s. See
[`data-model.md`](references/data-model.md) for section types, the shared `frame` options, and
the CTA union. Once a layout is chosen, its image spec follows from
[`surfaces.md`](references/surfaces.md); do not decide aspect ratio or transparency by hand.

**Set `organizations.theme` to the same palette as the imagery.** The style axis colors the
pictures; the tone bands, buttons and links come from `theme`, which is raw CSS custom
properties. Leave it empty and the platform default applies, which is green: a clinic built
entirely in navy shipped with a green closing CTA band because the images were styled and the
theme never was. The block to write is in
[`art-direction.md`](references/art-direction.md). Check the `tone: primary` band afterwards,
and note that a raw SQL update does not revalidate, so a cached page keeps the old theme.

**The `header` is MANDATORY and its nav MUST have depth (a working dropdown).** A flat header
with a lone logo is not acceptable. Give the header's entity a nav subtree TWO levels deep: a
nav root, then categories, then leaves. A nav item that HAS children renders as a **dropdown**
over those children; set the header option `dropdownStyle: "mega"` and give each leaf an `icon`
plus a short `slogan` (dropdown title) and a one-line `description` so the mega panel reads
richly. Categories are plain grouping nodes (a `name`, no slug); a top-level nav item with no
children is a single link. Leaves point to their `slug` page when one exists, else `"#"` (fine
for a launch, note the pending sub-pages). A shape that works: a nav root over 제품 (AI 응대,
예약 관리, 자동 페이지, 전환 분석), 솔루션 (피부과, 치과, 로펌), and 요금. The footer's link
columns can reuse the SAME category and leaf entities via extra `entity_edges`, since the graph
is a DAG, so nav and footer stay in sync without duplication.

**Reusing a node shares its copy too.** `slogan` and `description` belong to the entity, not to
the edge, so a node that is both a nav leaf and a feature card says the same thing in both
places. Nav and footer links want the same short label, which is why that reuse is free. A nav
leaf and a feature card do NOT: the dropdown wants a terse title and the card wants a headline.
When they need different copy, give the card its own entity with an EMPTY slug and leave the
real slug on the leaf. See [`data-model.md`](references/data-model.md).

**The org `logo` shows uncropped in the nav** (`OrgBrand` renders it `object-contain`, not a
cropped circle), so a wordmark or shaped glyph is fine. Just make sure `organizations.logo`
points at a real transparent PNG or SVG, not a placeholder.

**Make the hero an inset rounded panel.** Set `inset: true` on it. The section then floats with
margin on all four sides, rounds its corners, and `overflow-hidden` clips whatever fills it, so
a background image or video is a rounded showpiece rather than a slab welded to the viewport
edges. It also takes a minimum height of the screen less the inset margins and centres its
content vertically, which is what makes it read as a hero rather than a tall band. Both
reference orgs lead with an inset hero.

`inset` composes with the two ways a hero carries media, and they are different heroes:

- **A backdrop.** `background: true` with a `scrim` backdrop, and the copy sits over it. The
  image or video fills the panel and the rounding clips it. This is the clinic and place hero.
- **A product screenshot.** `background: false` and a wide app-UI image on the hero entity, which
  renders as bottom-bleed media below the heading and is clipped by the same rounding. This is
  the `hero-ui` surface, the classic headline-then-dashboard hero: `--shot ui-screenshot` at
  `21:9`.

**"Delete these components" from a user means STOP USING them on THIS org's page, never delete
the shared body component source.** Section renderers are multi-tenant, so many orgs render the
same components. To drop one from a page, `DELETE` its `sections` row and swap in a different
layout; do NOT remove the React component or its layout enum, which would break every other
tenant using it. Before treating a "remove component" request as a code change, check
`select o.slug, s.type from sections ...` for other orgs on that type.

**Give the page rhythm, alternate down the stack:**

- **`tone`**, don't paint every band the same. Alternate a plain `background` with an accent,
  cycling the accents so emphasis lands in a pattern: background, secondary, background,
  foreground, background, primary. The colored bands are where emphasis and the CTA live, so
  end on a `primary` band carrying the closing `reservation_form` or secondary CTA.
- **`align`**, alternate the title-group alignment section to section: center, start, center,
  start. A run of same-aligned headings reads flat; alternating gives a vertical zig-zag.
  (`split` sections are always `start`.)
- **`shot` and `surface`**, vary what the images depict and how they meet the page, and leave at
  least one band with no image at all. This is the rhythm section of
  [`art-direction.md`](references/art-direction.md).

**Layouts worth reaching for.** A `photo-card` features section pairs with bottom-anchored
transparent images, so the heading fuses with the figure rising below it. A `carousel`
autoplays. `screens`, and `framedMedia: true` on any card layout, turn a section into product
screenshots. `faqs` (accordion) and a `content` CTA band round out a full landing. A content
section's non-background image renders as bottom-bleed media melting into the tone band, so
those images must be wide AND transparent: `21:9`, `--transparent`, `--fill-width`.

---

## Credentials

`imagegen.py` reads the Gemini key from `--key` or `GEMINI_API_KEY`. The real key lives in
`skills/entity-setup/.env.local`, gitignored and never committed. Source it before
running the local path:

```bash
export $(grep -v '^#' skills/entity-setup/.env.local | xargs)
```

Use a project key with billing enabled; the image models require it. **Never put the real key in
a tracked file**, since this skill is checked into the repo.

higgsfield uses its own CLI session, not this key.
