# Data model: what you're filling in

Three tables make a landing page. Source of truth is the impl files; this is the working
summary. Verify field names against the impls before writing rows, schemas evolve.

- `packages/framework/src/impl/entity.ts`, `product.ts`, `section.ts`
- `packages/framework/src/sections.ts` (section options, CTA union, `loc`, field-role map)

## Contents

- [`entities`: the ONE content primitive (a graph)](#entities-the-one-content-primitive-a-graph)
- [`products`: commerce rows](#products-commerce-rows)
- [`sections`: the page composition](#sections-the-page-composition)
- [How images map to the model](#how-images-map-to-the-model)
- [Writing rows](#writing-rows)

## `entities`: the ONE content primitive (a graph)

Every piece of visible content is an entity node. Nodes form a **graph**, not a tree: a node
may have several parents, each via an `entity_edges` row (`parent_id`, `child_id`,
`position`). A root simply has no inbound edge. The landing walks a section's entity
subtree: **root, children, grandchildren**.

Fields (all default-able; `loc` = `{en, ko, ja?, zh?}`):

| field         | role |
|---------------|------|
| `name`        | short internal handle + the section `tag`/badge + the picker/chip label. Single-language, stable, the search/sort key. |
| `label` (loc) | the localized display twin of `name` for visible nav/footer/tag copy (`pick(label, locale) || name`). |
| `slogan` (loc)| the section **heading** by default. |
| `description` (loc) | the section **body** by default. |
| `image`       | a URL, hero backdrop, feature/card media, logo. Phase 1 fills this. |
| `icon`        | a hugeicons name (e.g. `"ServerIcon"`) for glyph renderers. NOT an image. |
| `slug`        | non-empty ⇒ this node is a **page** at `/slug`, and cards that render it auto-link there. Empty ⇒ not a page. |
| `position`    | order (also carried per-edge for ordering under a specific parent). |

Which field fills which role is overridable per section. `fields` maps each of
`tag`/`heading`/`description` onto one of `name`/`slogan`/`description`/`none`, so ONE entity
can headline in one section and be a tag in another. Default: `tag=name`, `heading=slogan`,
`description=description`.

**Constraints an insert will actually hit.** These are `NOT NULL` with a default, so "no value"
is the **empty string or empty object, never null**. Passing null aborts the whole transaction,
and psql writes that error to stderr while the successful statements go to stdout, so a script
that prints only stdout reports a silent rollback as success.

| Column | Definition |
|---|---|
| `entities.image` | `text not null default ''` |
| `entities.icon` | `text not null default ''` |
| `sections.cta` | `jsonb not null default '{}'::jsonb` |
| `sections.options` | `jsonb not null default '{}'::jsonb` |

**`slug` is uniquely indexed per org, but only when it is non-empty.** The index is
`entities_org_slug` on `(organization_id, slug) where slug is not null and slug <> ''`. So many
entities may carry an empty slug, and two entities in one org may NOT share a real one. When the
same thing appears twice on a page, a nav leaf and a feature card for the same treatment, that
is ONE entity with two parents through `entity_edges`, not two rows.

**Reuse costs you the copy, because `slogan` and `description` live on the ENTITY, not on the
edge.** A node used in two places says the same thing in both. That collides with what the two
places want: a nav dropdown wants a terse title, a feature card wants a headline with a point of
view. Sharing one node between them shipped "기미와 잡티" as a card heading where the section
needed "색소는 한 번에 지우지 않습니다", and nothing failed, it just read like a label. Decide
per node:

- **The card is the page.** Use one shared node and write its copy to work as a card heading.
  The dropdown carries that longer line too, which is usually acceptable.
- **The two roles need different copy.** Use two entities. Give the card an empty slug so the
  unique index allows it, and let the nav leaf keep the real slug and the page.
- Either way, `fields` can re-map which field fills which role per section, so check that before
  splitting a node.

**Shape to build:** one root per section that needs its own content (a hero root, a
features-group root, a faq-group root, footer-group roots). The group root's children are
the individual cards / questions / links. This is why "generate an image for every child of
an entity" (Phase 1 batch) is the natural unit, a features group's children are exactly one
cohesive image set.

## `products`: commerce rows

`name`, `status` (`active` | `draft` | `archived`), `price`, `inventory`, and `entity_id`
(the content entity this product maps to, optional). Products are scoped by `organization_id`
(ambient). A product's *pictures and prose* live on its linked entity; the product row is the
commerce record.

## `sections`: the page composition

A section is THIN: a renderer `type`, the `entity_id` it renders, a `path` (which page; `""`
= home; `header`/`footer` are global), a `position`, per-type `options`, and `cta`s. No
content of its own, it walks the referenced entity's subtree and the `type` decides how.

**Types:** `header`, `footer`, `content`, `features`, `faqs`, `logos`, `steps`, `stats`,
`testimonials`. (There is no separate `hero`/`cta` type, a hero is a `content` section with
`background: true` + `size: lg`; a closing pitch is a `content` section with a tone band +
CTAs.)

**Shared `frame` options** (on every body section's `options`):
- `tone`, `background` | `muted` | `primary` | `secondary` | `foreground`. The section
  band's color scheme; copy flips to the matching foreground. **Vary tone across sections
  for rhythm** (e.g. background, muted, background, primary CTA band).
- `size`, `sm` | `md` | `lg`. Type scale. `lg` for a hero / closing band, `sm` for a dense
  strip.
- `inset`, float the section as a rounded inset panel.
- `split`, title group beside the body instead of above.
- `background`, paint the section entity's `image` as a full-bleed backdrop (copy inverts).
- `fields`, which entity field fills each role (see above).

**Per-type knobs.** `sections.ts` is the source of truth and these enums grow, so check it
rather than trusting this list.

| Type | Layouts | Also |
|---|---|---|
| `features` | `grid`, `screens`, `photo-card`, `gallery`, `overlay`, `bento`, `slider`, `carousel`, `expandable`, `accordion`, `accordion-numbered`, `tabs`, `showcase`, `team`, `timeline`, `collage`, `zigzag` | `columns` 1 to 4, `bleed` (full-width track for `slider` and `carousel`), `framedMedia`, `cta` |
| `faqs` | `accordion`, `grid` | `columns`, `defaultOpen`, `allowMultiple` |
| `logos` | `row`, `grid`, `grid-bordered`, `orbit`, `radial`, `connector`, `cards` | `columns`, `header`, `mono` |
| `marquee` | no layout; a `variant` union of `marks` (small, `mono`) and `gallery` (large, `size`, `rounded`) | `reverse`, `duration` |
| `steps` | `row`, `row-numbered`, `grid-divided`, `timeline`, `stack` | `connector` |
| `stats` | `strip`, `grid`, `hero-metric` | `animate` |
| `testimonials` | `grid`, `spotlight`, `case-study`, `slider` | |
| `header` | `stacked`, `split`, `inline` | `dropdownStyle` |

Which of those need an image per child, and at what aspect ratio, is
[`surfaces.md`](surfaces.md).

**CTAs**. `cta.primary` and `cta.secondary`, a discriminated union by *what it does*:
`none`, `link` (has `href`), `ai` (open chat), `customer_form`, `reservation_form`, `email`
(inline capture + `caption`). Reserved kinds carry only a `label`; the surface they open is
built generically from the org's impls + custom fields.

## How images map to the model

Images live on entities, never on sections. The section decides how an entity's image is
treated.

| Role | The row that holds the URL |
|---|---|
| Hero or section background | the section's entity `image`, with `background: true` |
| Feature or card media | each CHILD entity's `image`, one Phase 1 set, one item per child |
| Product cutout, logo | a transparent PNG on the product's or logo's entity `image` |
| Feature glyph | `entities.icon`, a hugeicons name, NOT a generated image |

Which aspect ratio, transparency and anchoring each of those needs is
[`surfaces.md`](surfaces.md).

**A card links itself when its entity is a page.** `href` is resolved from the entity's `slug`,
so giving a treatment a real slug and a section on that path is all it takes: the card becomes
one whole focusable link and the view-transition morph keys off the same id. Nothing to wire per
card. The layouts that build bespoke markup rather than going through the shared card used to
drop that link, which looked identical and swallowed the click; they wrap now, so if a card is
still unclickable the cause is a missing slug or a missing page, not the layout.

## Writing rows

Entities and sections are `revalidating`, a write re-publishes the tenant's landing pages.
The actual write mechanism (framework write path vs. Supabase SQL, and which project +
storage bucket for image upload) is per-invocation and MUST be confirmed for the target org
before writing. This is prod content. Never invent FKs the ambient context sets
(`organization_id` is injected); order writes so a section never references an entity that
doesn't exist yet.
