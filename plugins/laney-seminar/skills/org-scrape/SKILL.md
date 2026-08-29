---
name: org-scrape
description: >-
  Collect everything publicly known about ONE business and normalize it into a typed corpus
  a builder can plan from: the official site walked in full (every nav leaf, not just the
  top pages), Naver Place and the entire official blog, industry platforms (강남언니 and
  바비톡 for clinics, 로톡 for law firms), and news. Reads image-baked content with vision,
  because Korean business sites bake price tables, event terms and doctor profiles into
  pictures. Emits `.scrape-out/{slug}/corpus-index.json` plus the raw pages, digests and
  downloaded imagery behind it. Works for a hospital or clinic, a law firm (법무법인), and a
  tax firm (세무법인), and follows whatever the business actually has rather than a fixed
  template. Use WHENEVER the task is to research, scrape, crawl, survey or gather data about
  a business, including "{상호} 스크래핑", "이 병원 조사해줘", "경쟁사 자료 수집",
  "홈페이지 긁어와", "블로그 전부 가져와". Input is usually just a NAME; a URL is optional.
  NOT for turning that corpus into pages, copy or imagery: that is `entity-setup`, which
  receives the corpus through `org-evidence` and `org-launch-prep`. NOT a standalone audit.
---

# Org Scrape: collect, then normalize

This skill owns the collection half of the landing pipeline and ends at a contract.

```
org-scrape       S1 COLLECT     parallel collectors under a FORCED checklist
                 S2 NORMALIZE   librarians merge into a typed index        Gate A
                 ─────────────  .scrape-out/{slug}/corpus-index.json
org-evidence     maps the corpus into the evidence ledger ([E-*] / [C-*] / source states)
org-launch-prep  reconciles, gates rights, obtains human approval, drafts the handoff
entity-setup     imagery, entity copy, sections
```

**Everything downstream may read only what this skill wrote.** The ledger and the plan cite
corpus refs and nothing else, so a fact that never made it into `corpus-index.json` cannot
reach the page. That is why the collection checklist is forced rather than best-effort.

Read [`references/corpus-format.md`](references/corpus-format.md) before writing any
artifact. That file is the contract, this file is the operating procedure.

## Position in the workspace

- `org-evidence` activates this skill **on demand**, never the other way round. This skill
  does not read `org-evidence`; it emits a corpus that `org-evidence` maps into its ledger.
  The mapping is [`references/evidence-handoff.md`](references/evidence-handoff.md).
- **Scope follows purpose.** For launch preparation (a landing, a callback, an entity graph)
  the forced checklist applies: a fact absent from the corpus cannot reach a page. For a
  presence audit, `org-evidence`'s deterministic HTTP collector is usually enough and this
  skill stays inactive unless a rendered surface is material to a finding.
- The `org-evidence` contract applies to every collector here: record each source as
  `connected`, `available-but-empty`, `not-connected`, `not-applicable`, or
  `access-failed`; never send cookies or credentials; never bypass a login or anti-bot
  control; do not call undocumented private endpoints; public visibility is not reuse
  permission. Where a playbook in `references/platforms.md` predates that contract, the
  contract wins and the playbook says so inline.

## Artifacts

All runs persist under `.scrape-out/{slug}/` at the repo root (gitignored):

| path | what |
|---|---|
| `raw/` | fetched pages, one file per URL |
| `digests/` | one compact digest per collector, 1,000 to 2,000 tokens each |
| `images/` | downloaded imagery |
| `readings/` | vision readings, one per image |
| `index-parts/` | per-family partial indexes, written incrementally |
| `corpus-index.json` | the merged typed index, the handoff artifact |
| `report.md` | what was collected, what was skipped and why |

## Resume first, every run starts here

A long run dies sometimes: a network drop, a killed session. The artifacts on disk are the
recovery point, so before doing anything, look at `.scrape-out/{slug}/` and **start at the
first missing stage.** Never redo finished work.

| present on disk | start at |
|---|---|
| nothing | S1, full collect |
| `raw/` and `digests/` for some sources | S1 for the MISSING sources only, plus any gap marked `retryable` |
| all digests, no `corpus-index.json` | **S2** |
| `corpus-index.json` present | done, hand off to the caller (see Handoff) |

Announce the decision out loud ("digests 4/4 present, starting at S2"). Re-collect a source
only when its digest is missing or its gap is marked `retryable`.

## Subagent task spec, applies to EVERY spawned agent

Every collector and librarian prompt carries four fields. This is what prevents drift.

1. **Objective**, one sentence, singular.
2. **Output format**, the exact artifact: digest schema, index-part schema, file path.
3. **Sources and tools**, which URLs, refs and scripts it may use.
4. **Boundaries**, what it must NOT do. For a collector: "do not summarize into prose, emit
   the digest schema, write raw to disk."

Subagents are context filters. They may burn tokens reading, but they RETURN only the
compact artifact. The main thread never ingests raw crawl output.

---

## Scope profile — decide this BEFORE S1, and say which one you chose

**Collect what the consumer can actually consume.** A run's cost is set here, not by how
thorough each collector is. Measured on one clinic: a full run took ~50 minutes end to end,
and a third of the collected material was never read by the write path that consumed it.

| profile | the consumer | collect | skip |
|---|---|---|---|
| **`seminar-min`** | a live-session demo: catalog + grounded chatbot, ~10 min | **own site only, single source.** The master catalog page (every treatment's name + published price), event/package pages **top 10 categories**, FAQ / hours / doctors / address / aftercare / policies (the chatbot's grounding), footer legal block | ALL external platforms (`skipped-by-profile`), treatment detail pages, blog entirely, imagery, channels beyond name+URL. **S2 collapses**: single source → nothing to merge; the catalog maps straight to products; promotions are not created at all (no 정가 evidence, none claimed) |
| **`seminar`** | `entity-setup` seminar path → laney MCP (entities, products, promotions, one prompt) | treatment catalog + descriptions (top ~15 details), **all prices and events**, the price-primary platform, org profile / hours / doctors / FAQ / aftercare / visit process | blog post **bodies** (titles+dates only), image download and vision reading, channel depth beyond name+URL, cases, press, secondary platforms |
| **`launch`** (default) | `org-evidence` → `org-launch-prep` → `entity-setup` full path | everything below, including Phase 2 vision reading and the full image inventory | nothing |
| **`audit`** | `org-evidence` presence audit | this skill usually stays inactive; activate only for a rendered surface a finding depends on | the rest |

`seminar-min` trades breadth for speed but **not correctness** — the floor below applies in
full, and its single-source design is precisely what makes it the safest profile: with one
source there is no cross-source conflict to mis-resolve and no platform-only 정가 to
mistake for a discount. Its S2 is a **compile, not a merge**: one pass over the catalog and
event pages into `corpus-index.json` (still deduped by `(name, price, option)`, still Gate
A), no librarian fan-out. Pair it with the chatbot rules in
`entity-setup/references/seminar-mcp-path.md` so the bot answers "확인 후 안내드리겠습니다"
for anything outside the thin corpus instead of guessing.

Announce the profile out loud at the start ("seminar profile: skipping blog bodies, imagery,
secondary platforms") and record it in `report.md`. A downstream reader must be able to tell
an intentional scope cut from a collection failure — **a skipped-by-profile source is still a
written entry**, state `skipped-by-profile`, not `gap`.

### The correctness floor — what no profile, and no "make it faster" instruction, may cut

A thin corpus that is right beats a broad one that is wrong. **Coverage is negotiable;
provenance is not.** Every observed wrong fact in this skill's history came from one of the
rules below being skipped, not from collecting too little:

1. **A fact with no raw file behind it does not enter the corpus.** One run reported a
   사업자등록번호 it had not written to raw; a later run reported the same field absent
   after a read that structurally could not see it. Both were wrong in opposite directions.
2. **Prices are transcribed, never computed.** No rounding, no unit conversion, no VAT math.
3. **`regular_price` and `discount_pct` only when a source states them.** A badge reading
   "EVENT" is not a discount; measured, several EVENT-badged items matched the clinic's own
   everyday 시작가 exactly.
4. **Cross-source disagreement is recorded, never averaged or silently resolved.** Own-site
   is canonical for identity; both figures and both sources survive into `conflicts`.
5. **One organization per corpus.** Never merge two businesses' facts, and never write into
   a tenant that already holds someone else's rows.
6. **Dedup before handoff.** A cross-listed SKU that reaches the database makes every later
   price answer ambiguous.

**The fastest correct configuration is single-source**, because rules 4 and 6 stop having
anything to resolve: collect the clinic's own site only, take its published prices as
authoritative, assert no discount, and let the platforms go. That is faster *and* safer than
a broad multi-source run — the two goals point the same way here, so when a speed
instruction and a rule above collide, the rule wins and the speed comes from cutting sources
and pages instead.

### `seminar-min` fallback — the clinic has NO homepage

Some owners have no website at all. The profile still runs; the source ladder changes:

1. **Discovery**: DuckDuckGo `"{병원명} {지역}"` and `"site:gangnamunni.com {병원명}"`.
   The 강남언니 desktop search page does not respond to URL queries (measured), but DDG
   reliably surfaces the hospital page (`gangnamunni.com/hospitals/{id}`) — that link is
   the way in. Confirm identity by address/phone before collecting anything.
2. **Primary source becomes 강남언니**: events with prices (open each event's detail
   page — the list under-reports), doctors, address, hours, ratings. **Label every price
   `source: gangnamunni`** — these are platform-listed prices, and the chatbot prompt must
   say so ("강남언니 게시 기준"). 정가/할인율은 강남언니가 명시한 값만, 그대로.
3. **Cross-check grounding** (hours/address/phone) against Google Maps (try once; record
   a gap if denied) and hospital directory sites that DDG surfaces.
4. **Naver (map/place/blog) stays `not-connected`** — the whole naver.com domain is
   blocked by browser policy (measured). Record it; do not retry in a loop.
5. **NO platform imagery on the landing.** Public visibility is not reuse permission;
   a platform-hosted photo must never become the clinic's hero image. This mode ships a
   text-only page + chat; the owner adds photos in the dashboard.
6. **The owner is a first-class source.** They are present and authoritative — hours,
   prices, and corrections they state out loud enter the corpus as `source: owner`,
   and outrank platform listings on conflict.

### Thin homepage — ask the owner instead of guessing

A homepage can exist and still be thin: 시술만 있고 가격이 없다, 진료시간이 없다,
FAQ가 없다, 원장 소개만 있다. In `seminar-min` the owner is sitting right there, so a
gap is a question, not a dead end. **Never fill a gap by inference, by another clinic's
page, or by a "일반적으로" number.**

Trigger the interview when any of these is true after S2:
- priced offerings < 5, or more than half of offerings carry no price
- 진료시간·주소·전화 중 하나라도 비어 있음
- FAQ 0건

Ask in small batches, in the owner's language, one screen at a time — never a
questionnaire dump. Show what you already have so they only fill the holes:

> "홈페이지에서 시술 12개를 찾았는데 가격이 적힌 게 3개뿐이라, 나머지는 챗봇이
> '확인 후 안내드리겠습니다'로만 답하게 됩니다. 지금 대표적인 것 몇 개만 불러주시면
> 바로 넣을게요. 울쎄라, 슈링크, 보톡스 순으로 얼마인가요?"

Rules for owner-sourced facts:
1. Record them as `source: owner`, with the date. They outrank platform listings on
   conflict, and rank below the clinic's own published page only when the page is current.
2. **Read the number back before writing it.** "울쎄라 100샷 60만원, 맞을까요?" A
   misheard price is worse than a missing one.
3. If the owner is unsure, do NOT write it. Leave the gap and tell them the chatbot will
   say "확인 후 안내드리겠습니다" for that item until they fill it in the dashboard.
4. 시술 효과·부작용·기간에 대한 문장은 원장님이 말한 범위를 넘지 않는다. Do not
   compose medical claims from general knowledge.
5. Ask for 진료시간·휴진일·주차·위치 explicitly if missing — these are the most common
   chatbot questions and the owner answers them in seconds.

Keep the batch short (3~5 items), write what you got, then continue. If the owner would
rather skip, that is fine: a thin corpus with an honest chatbot is the floor this profile
guarantees.

The corpus is thinner, so the never-wrong prompt matters more: more "확인 후
안내드리겠습니다", never a guess. Record `profile: seminar-min (no-homepage fallback)`
in report.md.

### Image URLs ride along for free — even in `seminar-min`

The profile skips image *downloads* and vision reading, but every visited page's
**`og:image` URL** (and the hero `<img src>` when og:image is absent) costs one
regex on HTML you already fetched. Collect them:

- homepage → `organization.hero_image`
- each treatment/event page → that offering's `image` field in the corpus

These are the clinic's own assets, referenced by URL only — no download, no
generation, no rights questions. Downstream, entity-setup attaches them to
entities and the landing hero; measured on one clinic this alone made the
main page look finished. A page with no og:image simply leaves the field empty.

Three cuts carry most of the saving, and each has a real cost — take them only in `seminar`:

- **Blog bodies.** The seminar write path has no destination for posts. Titles and dates
  still cost nothing and help the chatbot know what the clinic writes about.
- **Imagery.** Skipping the download gate and Phase 2 vision is safe **only when prices are
  published as text.** Check first: if the catalog page shows no prices, the prices are baked
  into images and vision is mandatory — one clinic's homepage yielded 0 text prices and its
  whole commerce graph lived in 18,000px infographics. Never skip vision on a site whose
  prices you cannot find in text.
- **Secondary platforms.** Collect the one that actually carries 정가 first. On one run the
  other two cost 12 minutes and returned zero live events. In `seminar`, treat them as
  optional and record `skipped-by-profile`.

## S1, COLLECT

Run `scripts/preflight.sh` once first, unless you were told a parallel run is already
active. Then load the key:

```bash
export $(grep -v '^#' skills/org-scrape/.env.local | xargs)
```

### Phase 0, scout

Resolve the NAME to the official homepage. Verify identity by address and phone, never
settle for a directory listing. Detect the **industry** and record both. Industry drives the
collector roster; see [`references/industry-profiles.md`](references/industry-profiles.md).

### Phase 1, collectors in parallel

Open the browser pane once from the main thread (`preview_start`), then **spawn every
collector in a single message** so they run concurrently — one agent per source, each with
its own tab. 4 to 8 tabs is the working range; past 8 they contend and wall-clock stops
improving.

**A source with more than ~12 pages gets sharded, not looped.** Discover its URL list once
(sitemap or one nav read), split the list into numbered slices, and give each slice its own
agent — a single agent walking 33 pages took 20.8 minutes and set the whole phase's
wall-clock. The dispatch shape, the sharding rules, and the per-agent tab contract are in
[`references/claude-browser.md`](references/claude-browser.md).

The per-industry source list and the forced checklist live in
`references/industry-profiles.md`. **Every listed source ends in exactly one of two states:
`collected`, or a written `gap` entry with a reason. Silent skipping is a defect** and it is
how an earlier run lost an entire Naver blog.

Non-negotiables:

- **Own site**: a full nav walk, every menu leaf, not just the top pages. Then
  `scripts/extract_images.js`.
- **Naver**: Place, plus the **entire official blog through
  `scripts/fetch_naver_blog.py`** when one exists. 병원 후기와 안내글, 로펌 칼럼이 여기
  들어 있고, 이 코퍼스가 사례와 언론보도와 포스트를 채웁니다.
- **Industry platforms**: for a clinic, 강남언니 + 여신티켓 (+ 바비톡) are the **primary
  source of prices and live events** — a Korean clinic homepage carries almost no treatment
  prices (medical-ad regulation), so the platforms' event prices are the only public price
  source. Collect each treatment's event price, regular price, options, and period; do not
  finish a clinic run with an empty commerce graph just because the homepage had no prices.
  **Read each platform's robots.txt for the group that names `Claude-User`, not `*`** — all
  three currently permit this browser (강남언니 excludes `/reviews` and `/community`;
  여신티켓 asks for a 5-second delay). Per-platform detail and the measured verdicts are in
  `references/platforms.md`. For a law firm, 로톡.
- **News**: for law and tax, search the news tab for `"{상호}" 변호사`.

Each collector writes raw to `raw/` and returns a **digest**: counts, notable facts, an
asset inventory, and corpus refs. Schema is in `references/industry-profiles.md`. Keep it
to 1,000 or 2,000 tokens. No prose dumps.

### Phase 2, vision read

Korean business sites put prices, event terms, before-and-after sets and doctor profiles
inside images. Text-only crawling misses them entirely, which is the reason this phase
exists.

**Default reader: Claude subagents, in parallel — no external vision key.** The download
gate runs first (geometry only, no key), then a fleet of subagents reads the downloaded
image files directly with the Read tool and emits one reading per image. This keeps the run
inside the harness the operator is already signed in to; no Gemini key sits on the machine
or on a server. The full contract — the classification vocabulary, the reading schema, the
batch/dispatch spec, and the mechanical re-grade — is
[`references/claude-vision-reading.md`](references/claude-vision-reading.md).

```bash
python3 scripts/download_images.py ...     # geometry gate only, NO key, writes manifest.json
# then: spawn N Claude subagents over manifest items → readings/{sha256}.json
#       (see references/claude-vision-reading.md for the batch size and task spec)
# then: mechanical re-grade over readings/ (demote logo / price-table / strip / banner)
```

**Fallback: the Gemini script**, only where a batch is too large to be worth subagent
wall-clock and a key is actually available. `scripts/read_images.py` calls Gemini directly
and needs `GEMINI_API_KEY`; `scripts/read_images.py --regrade` is the mechanical second
pass. Prefer the Claude path for a seminar or any run on a machine that must not hold a key.

The re-grade pass (either reader) uses the readings to demote candidates that cannot be a
card: a logo, a price table, a page strip, a text-baked banner. The download gate judges
geometry alone because it runs before vision, so without the re-grade a logo lands in a
doctor's portrait slot and a 1-to-12 strip lands in a grid. Both have happened.

### Browser rules

- **Renderer: Claude Browser (`mcp__Claude_Browser__*`) is the default.** It renders sites
  that refuse headless crawlers (measured: 강남언니 403 → renders; 여신티켓 empty shell →
  renders), it ships with the harness so any operator can run this skill, and it holds no
  keys or logged-in sessions. The full playbook, including the tab-isolation rule that makes
  parallel collection safe, is [`references/claude-browser.md`](references/claude-browser.md).
- **Parallelism = one tab per agent.** The pane is shared across the session, so every
  spawned collector opens its own tab with `tabs_create {foreground:false}` and passes that
  `tabId` to **every** browser call, then closes it. A call without `tabId` lands in another
  agent's tab and silently returns the wrong business's data. Only the main thread calls
  `preview_start`; no collector calls `tabs_select`.
- **Fallbacks, in order:** `aside` MCP (real Chrome — use it when a surface needs the
  **owner's own logged-in session**, e.g. a 파트너센터), then the `agent-browser` CLI headless.
  Never `--headed`, never `AGENT_BROWSER_HEADED`. With agent-browser, one session per agent
  with its own `--profile /tmp/ab-<name>`; only the main thread runs preflight.
- **Never WebFetch or WebSearch for the crawl.** JS-heavy Korean sites return silent garbage
  without a renderer, and the garbage looks like a successful fetch.
- **Check `{origin}/robots.txt` before crawling a domain and record the verdict** in the
  digest's `robots` field, quoting the group you matched. **Find the group that applies to
  you, which is usually not `*`:** under RFC 9309 a named group wins and does not inherit
  `*`, and this browser is **`Claude-User`**, not the `ClaudeBot` training crawler. A site
  that allows `Claude-User` while setting `Disallow: /` for `*` is open to this skill.
  Honour any `Crawl-delay`. Only when no group names you and `*` is `Disallow: /` do you
  stop: record `not-connected` and route to owner-connected data. The gate is not defeatable
  from inside this skill — changing user agent, rotating address, or clearing an interstitial
  to get around a genuine refusal is out of scope here and under the `org-evidence` contract.
- WAF-blocked (NinjaFirewall, a Cloudflare challenge, a 403, an empty shell) is a recorded
  `access-failed` for that source, not a reason to bypass it. Return partial results plus
  the error.
- On launch failure: close your own tab or session, retry once, and if it still fails return
  partial results plus the error. Two attempts maximum, and no WebFetch fallback.
- Politeness: pause briefly between requests to the same domain, and cap each site at
  **50 pages**.

Playbooks: [`references/claude-browser.md`](references/claude-browser.md),
[`references/platforms.md`](references/platforms.md) and
[`references/dynamic-capture.md`](references/dynamic-capture.md).

---

## S2, NORMALIZE, then Gate A

**Delegate this. Never normalize in the main thread.** A real corpus is 40 or more raw
pages, 200 or more image readings, and 100 or more blog posts. Reading all of it into the
orchestrator stalls the run; one observed attempt ran 50 minutes and produced nothing.

Instead:

- Spawn **one librarian subagent per collection family**: offerings and prices, people,
  cases and before-and-after, events and promotions, posts and extras. Each reads ONLY its
  own raw refs and **writes a partial index to `index-parts/{family}.json`**. Partials are
  incremental, so a crash never loses finished work.
- The main thread then **concatenates the parts** into `corpus-index.json` and computes the
  `inventory` header. Merging small typed files is cheap; re-reading raw is not.

### Start each librarian the moment ITS shards land — do not wait for all of S1

**S1 → S2 is a pipeline, not a barrier.** A librarian depends only on the shards that feed
its family, and waiting for the slowest unrelated shard is pure idle time. Measured: the
content family needed only the core shard (done at 14.8 min) but was started after the whole
of S1 (15.6 min); the people family needed core + platform and could have started at 14.8.

Map the dependency once, then launch each librarian as its inputs complete:

| family | waits only on |
|---|---|
| commerce (offerings + promotions) | the catalog shard + the pricing shard (+ the platform shard if one runs) |
| people-org | the core shard (+ platform, for ids and ratings) |
| content (faqs, posts, extra) | the core shard |
| cases / press | whichever shard collected them |

### Shard a heavy family too — the same rule as S1

**A librarian is a loop like any other.** Measured: one commerce librarian merging a 56-item
catalog against 57 event items and 7 platform events took **24.4 minutes** and became the
run's bottleneck *after* S1 had been sharded down to 15.6. Sharding S1 alone just moves the
bottleneck downstream.

Split a family when its input exceeds roughly **40 items**:

- **Shard by category**, and give each shard an explicit item list, exactly as in S1 — the
  slice must not be left to judgement or items fall between two shards.
- Each shard writes `index-parts/{family}-{slice}.json`; the main thread concatenates them
  along with everything else. Counts add, `conflicts` and `notes` concatenate.
- **Cross-shard dedup is the main thread's job, not a shard's.** A shard cannot see another
  shard's items, so it cannot collapse a duplicate that straddles the boundary. After
  concatenating, run one dedup pass over the merged list keyed on `(name, price, option)`
  and record every collapse in `notes`. This is cheap on typed rows and it is where a
  cross-listed SKU is caught — one run wrote a duplicate pair all the way into the database.
- A conflict that spans two shards surfaces the same way: same key, different price, both
  sources kept.

The merged shape follows `references/corpus-format.md`, including the `extra` collection for
content that no template anticipated, plus an index header:

```jsonc
{ "inventory": { "offerings": 34, "offerings_with_price": 23, "people": 6,
    "before_after_pairs": 12, "events": 7, "reviews": 40, "blog_posts": 160,
    "facility_images": 9, "press": 0, "extra": ["columns(31)"] },
  "conflicts": [ "…" ], "missing": [ "hours: weekly schedule unknown" ] }
```

Dedup, resolve conflicts with the official site as canonical, and flag gaps. Raw stays on
disk. Every item carries a stable ref such as `off-lifting` or `img-3fa2…`, because
**downstream may cite only these refs.**

**Gate A, mechanical:**

- the index parses,
- every ref is unique,
- the vertical's minimum viable inventory is met. A clinic with 0 offerings means collection
  failed. Fix S1, do not proceed.

## Handoff

When Gate A passes, write `report.md` (what was collected, what was skipped and why, which
gaps are `retryable`) and return the corpus locator plus the source-state table to the
caller. In this workspace the caller is `org-evidence`, which maps the corpus into its
Markdown ledger by [`references/evidence-handoff.md`](references/evidence-handoff.md);
`org-launch-prep` and `entity-setup` read the ledger, never the raw corpus. Do not plan
pages, write copy, or generate imagery here. Those are `entity-setup`'s job and it will
refuse work that arrives half-built.

## References

- [`references/corpus-format.md`](references/corpus-format.md), the output contract. Read
  it first.
- [`references/evidence-handoff.md`](references/evidence-handoff.md), how the corpus becomes
  `org-evidence` ledger entries, and the two policy decisions that gate collection depth.
- [`references/industry-profiles.md`](references/industry-profiles.md), the forced checklist
  per industry and the per-source digest schemas.
- [`references/platforms.md`](references/platforms.md), per-platform crawl playbooks.
- [`references/dynamic-capture.md`](references/dynamic-capture.md), JS-rendered and
  infinite-scroll capture.
- [`references/claude-vision-reading.md`](references/claude-vision-reading.md), the default
  Phase 2 reader: parallel Claude subagents read images with no external vision key.
- The graph the corpus eventually feeds is the `entities` / `entity_edges` contract in
  `skills/entity-setup/references/data-model.md`. Read it when deciding whether a discovered
  collection is worth keeping.

## Scripts

| script | what |
|---|---|
| `scripts/preflight.sh` | browser session hygiene, run once per run |
| `scripts/extract_images.js` | pull image URLs and geometry out of a rendered page |
| `scripts/download_images.py` | fetch candidates, gate on geometry |
| `scripts/read_images.py` | vision read every image, then `--regrade` |
| `scripts/fetch_naver_blog.py` | full-text pull of a Naver blog |

`read_images.py` needs `GEMINI_API_KEY`. It looks in `${CLAUDE_SKILL_DIR}/.env.local`, then
falls back to `skills/org-scrape/.env.local`, then to the process environment. That file is
gitignored (`.env*`) and must never be committed.
