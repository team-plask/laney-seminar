# Seminar / owner self-service path — corpus → laney MCP

The default entity-setup flow assumes a prepared `org-launch-prep` handoff and a SQL/storage
write path. This file is the lighter path for a live seminar, where a clinic's own owner
runs the installed skills against their own site and seeds their own Laney workspace through
the laney MCP. Nothing here replaces the full path; it is the subset that works inside the
MCP boundary with the owner as the sole authority.

## When this path applies

- The org's **owner is present and is the authority on their own facts** — a doctor setting
  up their own clinic. `org-launch-prep`'s human-approval gate is that person, live, so the
  scattered-source reconciliation and separate approval step collapse.
- The write path is the **laney MCP**, not SQL and not storage upload.
- The goal is **"teach Laney the clinic's data"**, not "publish a finished landing." Sections
  and imagery are explicitly out of scope here (see Boundaries).

If the facts are about *another* business, are conflicting, or are unlicensed, do NOT use
this path — run `org-launch-prep` first.

## Input

An `org-scrape` corpus for the owner's site: `.scrape-out/{slug}/corpus-index.json` plus its
image `readings/`. Prices and promotions baked into images come from the Claude vision
readings (`org-scrape/references/claude-vision-reading.md`), so no vision key is needed. The
owner may also just state facts out loud; a stated fact from the owner is a valid source
because they are the authority.

## What maps to which MCP tool

Write in this order so a later row can reference an earlier one, and so a wrong row is easy
to spot before the next depends on it. `organization_id` is injected by the token; never
pass it.

| Corpus field | laney MCP tool | Notes |
|---|---|---|
| offerings (시술) | `entities__insert` | `name` + localized `label`/`slogan`/`description`; `slug` for a treatment that should be its own page. One entity per treatment. |
| people (의료진) | `entities__insert` | Only owner-verified name + role. Never write an unverified clinician. |
| priced offers | `products__insert` | `kind` (usually `one_time`), `name`, `price` (KRW integer), `status: active`. Price comes from the corpus / vision reading, never invented. |
| promotions (이벤트) | `promotions__insert` | `kind: event`, `name`, `benefit_type` (`price`/`percent`/`amount_off`/`gift`), `value`, `starts_at`/`ends_at` from the corpus. Draft unless the owner confirms it is live. |
| chatbot persona | `templates__insert` | `kind: prompt`. This is the org base prompt (`account_id` null) that `templateBody()` reads. Ground it in the collected 시술·가격·톤, and write the **never-wrong rules** below into its body. |

### The never-wrong rules — write these into every org base prompt

The seminar's promise is a bot that may know little but is never wrong about the clinic. A
thin corpus is fine **only if** the prompt makes the bot prefer "I'll check" over a guess.
Write these into the prompt body, adapted to the clinic:

- **가격은 절대 기억으로 답하지 않는다.** 반드시 가격 도구를 호출해 그 결과만 말한다. 도구
  결과에 없으면 "정확한 금액은 확인 후 안내드리겠습니다"라고 답한다 — 프롬프트 본문에 적힌
  숫자조차 인용하지 않는다.
- **자료에 없는 것은 추측하지 않는다.** "제가 가진 정보로는 확인이 어렵습니다. 전화(...)로
  확인해 드릴까요?"가 정답이고, 그럴듯한 답변이 오답이다.
- **시술 효과·기간·부작용은 병원이 명시한 문장 범위를 넘지 않는다.** 진단하지 않는다.
- **요일 한정 이벤트**는 방문 예정 요일을 먼저 확인한 뒤에만 안내한다.
- **평점을 단일 수치로 말하지 않는다** — 플랫폼마다 척도와 모수가 다르다.
- **corpus가 conflict로 표시한 사실**(도보 시간, 주차 등)은 병원 공식 안내만 말하고, 확인
  전화를 권한다.
- 할인·정가는 프로모션 데이터가 active일 때만 언급한다. draft 프로모션은 존재하지 않는
  것으로 취급한다.

## Boundaries — what this path does NOT do over MCP

- **No image uploads**: the MCP token carries no storage bucket. But `entities.image` as a
  **URL reference** (the clinic's own og:image, collected by org-scrape) is in scope — that
  is how Step 7.5 dresses the page without generating or uploading anything.
- **`entity_edges` and `sections.entity_id` are currently stripped at the MCP boundary**
  (LNY-1527, measured 2026-08-28). Products stay unlinked to their treatment entity, and
  Step 7.5's section bindings fail until the fix ships — attempt once, degrade gracefully.
- So the guaranteed deliverable is a **populated catalog + grounded chatbot + chat-ready
  page**; the composed visual home arrives with LNY-1527. Say so plainly to the owner.

## Verify before finishing

The point of the seminar is the owner seeing their own data go live in the consult path.
After the inserts, run `products__quote` with a treatment name the owner recognizes and show
that the chatbot's pricing tool returns the product just created — the same tool the live
consult bot calls. A promotion, if active and applicable, shows in the quote's
`promotions`/`final_price`. That round trip is the proof the seeding worked.

## Order of operations, end to end

1. `org-scrape` the owner's site (Claude vision reads image-baked prices; no key).
2. Read `corpus-index.json` + `readings/`.
3. **Check the org is empty of anyone else's data** — see "Isolate the org first" below.
4. `entities__insert` per treatment and per verified clinician.
5. `products__insert` per priced offer.
6. `promotions__insert` per current event.
7. `templates__insert` (`kind: prompt`) grounded in the collected facts.
8. `products__quote` to verify, and tell the owner what is left for the dashboard
   (treatment↔product links, section layout, images).

### Steps 4–7 are independent — run them in parallel, and shard the big ones

Because this path writes **no `entity_edges`**, a product does not reference its entity and a
promotion does not reference a product. Nothing in steps 4–7 depends on anything else in
steps 4–7. Running them in sequence is wasted wall-clock.

Measured on one clinic: 43 entity inserts took **17.6 minutes** (~25s each) and 95 product
inserts took **10.1 minutes**, run one after another in single agents.

- **Launch entities, products, promotions+template as three concurrent agents.**
- **Shard within each** on the same rule as `org-scrape`: entities by category, products in
  slices of ~25. Four shards turn 17.6 minutes into about 5.
- Give every shard an **explicit item list** from the corpus, never a rule for selecting its
  own — overlapping selection rules produce duplicate rows, and this path has no unique
  constraint to catch them.
- Each shard reports the ids it created; the main thread verifies the total count before
  moving to `products__quote`.

### Isolate the org first — a wrong-tenant row is the worst failure on this path

The MCP token is bound to **one** organization. Before any insert, `entities__list` and
`products__list` and confirm what is already there.

If the org holds **another business's** rows — a previous demo, a different clinic — stop and
tell the owner. Do not write alongside them. Measured consequence: an org still holding a
previous clinic's 20 entities, 3 products and **its org base prompt** got a second clinic's
data written in; `templateBody()` reads one org-level prompt and nothing controls which of
the two it picks, so the consult bot can answer as the wrong clinic, quoting the wrong city
and phone number. A stale treatment name that both clinics genuinely offer is invisible to
the eye and impossible to attribute later.

Deleting is the owner's call, not this skill's — surface the collision and let them clear it
in the dashboard, then write into a clean org.

### Step 7.5 — rough main page (landing quickstart)

After entities/products/prompt land, assemble a starter home so the chat page
doesn't open bare. **Validated recipe** (modeled on the jarada/BA tenants,
rendered end-to-end on a live demo tenant):

1. **Attach images first**: for each entity whose corpus offering carries an
   `image` URL, `entities__update {image}`. Hero image = `organization.hero_image`.
2. **Purpose entities** (these are presentation rows, position 44+, never part
   of the treatment catalog):
   - 병원 소개 — name=병원 이름, slogan=사이트의 대표 카피, description=신뢰 문구
     (상담가=게시가 등, 코퍼스 근거), image=hero_image
   - 대표 시술 — parent for the top 3 treatments (children via entity_edges)
   - 자주 묻는 질문 — parent + 3 child entities (질문=name, 답=description,
     코퍼스 FAQ에서 verbatim)
   - 상담 안내 — CTA copy entity
3. **Sections** (path "", positions 10/30/50/58):
   - content hero: entity=병원 소개, `{size:lg, align:center, inset:true,
     background:true, backdrop:scrim, fields:{tag:none}}`,
     cta primary `{kind:ai, label 'AI 상담하기'}` + secondary tel link
   - features carousel: entity=대표 시술, `{tone:muted, layout:carousel,
     columns:3, fields:{tag:none, heading:name, description:slogan}}`
   - faqs accordion: entity=FAQ, `{split:true, layout:accordion, defaultOpen:true}`
   - content CTA band: entity=상담 안내, `{size:md, tone:primary, align:center}`,
     same cta pair

⚠️ **LNY-1527 gate**: as of 2026-08-28 the MCP boundary strips `sections.entity_id`
and `entity_edges.parent_id/child_id`, so steps 2–3's bindings fail on insert.
**Degrade gracefully**: attempt once; on failure tell the owner the chat page
already works (`{slug}.preview.laney.app`, greeting + chat live without sections),
record that the visual page arrives with the LNY-1527 fix, and continue. Never
loop on the failing insert.
