# Claude vision reading — parallel subagents, no external key

The default Phase 2 image reader. It replaces the Gemini script
(`scripts/read_images.py`) with a fleet of Claude subagents that read the downloaded image
files directly through the Read tool. The output schema is identical to the Gemini path, so
the S2 normalize step and the compile that follows do not care which reader produced a
reading. Choose this path whenever the machine must not hold a vision key — a seminar on a
doctor's own laptop is the motivating case.

Why this works: the Read tool ingests PNG/JPG/GIF/WebP and presents the image to the model
natively, so a subagent given a local image path can classify it and transcribe its baked-in
text. Authentication is just the operator's existing Claude Code session. Nothing new is
provisioned.

## Inputs

`scripts/download_images.py` runs first (geometry gate, no key) and writes
`.scrape-out/{slug}/manifest.json`. Each item carries what a reader needs:

| field | use |
|---|---|
| `local` | path (relative to the run dir) of the downloaded image file — this is what the subagent Reads |
| `sha256` | stable id; the reading is written to `readings/{sha256}.json` |
| `category`, `width`, `height` | download-time geometry guess; the reading may correct it |
| `alt`, `page` | provenance hints; `page` is the source URL, kept as evidence |
| `reading.status` | `pending` means unread; skip `done`; a reader only touches `pending` and non-logo items |

## Reading schema (one JSON object per image)

Byte-for-byte the Gemini path's schema, so downstream is unchanged. Every field is
required; use an empty string or empty array for "not present", never null.

```jsonc
{
  "sha256": "…",                 // echo the manifest id so the merge is keyed
  "image_class": "price-table",  // what the image IS (routing) — enum below
  "kind": "price-table",         // data-bearing role: price-table | event-banner | treatment-info | photo | other
  "has_text": true,
  "subject": "람스 50cc",         // named doctor / treatment / device if the image labels one, else ""
  "text_raw": "…",               // ALL legible text in the image, verbatim
  "prices": [                     // [] when none
    { "treatment": "람스 1회", "price": "390,000원", "note": "이벤트가" }
  ],
  "promotion": {                  // empty strings when not a promotion
    "name": "", "period": "", "benefit": "", "condition": ""
  },
  "summary": "해운대점 람스 가격표, 부위별 3종"
}
```

`image_class` enum (routing target for the compile step):

`doctor-photo` · `staff-group` · `facility-interior` · `device-equipment` · `before-after`
· `procedure-photo` · `event-banner` · `price-table` · `treatment-info` · `logo` ·
`decorative-or-stock` · `other`

## Per-image reading instruction (give this to every subagent, per image)

> 이 이미지는 병원/의원 웹사이트의 이미지다. 두 가지를 하라.
> 1) 이미지가 무엇인지 분류하라 (image_class): 의료진 사진(doctor-photo)·단체
>    사진(staff-group)·시설 내부(facility-interior)·장비(device-equipment)·전후
>    비교(before-after)·시술 장면(procedure-photo)·이벤트 배너(event-banner)·가격표
>    (price-table)·시술 설명(treatment-info)·로고(logo)·장식/스톡(decorative-or-stock)·
>    기타(other).
> 2) 이미지 안 텍스트를 모두 읽어라(text_raw, 원문 그대로). 특정 대상(의사 이름·시술명·
>    장비 모델)이 있으면 subject에 적어라. 가격이 있으면 시술명·가격·비고를 prices[]에,
>    이벤트면 이름/기간/혜택/조건을 promotion에 넣어라. kind는 데이터 성격
>    (price-table/event-banner/treatment-info/photo/other). 텍스트가 없으면 has_text=false.

Read only what is legible. Do not infer a price that is not written, and do not translate
the baked text — `text_raw` is verbatim Korean. A blurred or cropped number is `note` +
best-effort, not a fabricated figure.

## Dispatch: parallel subagents

The main thread never reads images itself — that is what stalls a run. It partitions the
`pending`, non-`logo` manifest items into batches and spawns one subagent per batch,
concurrently.

- **Batch size: 8–12 images per subagent.** Small enough that one subagent's context holds
  the images and its readings; large enough that dispatch overhead stays amortized.
- **Concurrency: up to ~10 subagents at once** (the harness caps concurrent agents; excess
  batches queue and run as slots free). A 200-image corpus is ~20 batches.
- **Each subagent's task spec carries the four fields from the SKILL's S1 contract:**
  1. Objective: read this batch of images, emit one reading per image.
  2. Output format: write `readings/{sha256}.json` per image using the schema above; the
     subagent's returned text is a one-line count, not the readings (it wrote them to disk).
  3. Sources and tools: the listed local image paths, the Read tool. Nothing else — no
     browsing, no network.
  4. Boundaries: verbatim `text_raw`; never invent a price or a name; empty string / empty
     array for absent fields; do not read images outside the assigned batch.
- **Idempotent and resumable.** A reading already on disk for a `sha256` is skipped. A
  killed run re-dispatches only the batches whose `readings/` files are missing — same
  resume rule as the rest of the skill.

Subagents are context filters: each burns tokens looking at its images but returns only a
count, so the orchestrator never ingests 200 images.

## Mechanical re-grade (no key, no vision — pure logic over readings)

After the readings exist, demote thumbnail candidates that the geometry gate wrongly kept.
An image whose reading `image_class` is one of `logo`, `price-table`, `treatment-info`, or
`decorative-or-stock` cannot be a card thumbnail, whatever its aspect ratio. Set its
`thumbnail_candidate` to false in the manifest. `scripts/read_images.py --regrade` performs
exactly this pass and is safe to run against readings the Claude path produced, because the
schema is shared.

## Handing readings to the evidence ledger

Each reading is evidence about its image. In `references/evidence-handoff.md` terms: the
image URL (`page`/`src`) is the `[E-*]` locator, the reading time is `observed`, and any
extracted `prices` / `promotion` become `[C-*]` claims that cite that `[E-*]`. A price read
from an image cites the image, never the page that embedded it. Rights stay as
`references/evidence-handoff.md` sets them: own-site images are `published-only`, third-party
platform images are extraction-only.
