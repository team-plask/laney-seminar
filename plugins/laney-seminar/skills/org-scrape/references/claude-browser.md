# Claude Browser — the default renderer, and how to run it in parallel

This is the **default** browser for every collector in this skill. `aside` MCP and the
`agent-browser` CLI are fallbacks, in that order.

## Why it is the default

Three measured reasons, all from the 2026-08-25 run:

1. **It renders what headless cannot.** The headless `agent-browser` run got `403 Forbidden`
   on 강남언니 and an empty search shell on 여신티켓. The same two sites open normally in
   Claude Browser, returning treatment names, 정가, 할인율, 이벤트가, 평점 and 리뷰 수 as
   plain text on the first read.
2. **Every operator already has it.** It ships with the harness. `aside` is one person's
   local setup, so a skill that depends on it cannot be handed to a seminar room full of
   원장님들. This was the blocker that made the previous run un-reproducible.
3. **It carries no credentials of its own.** It is a clean browser pane, not the operator's
   logged-in Chrome. Nothing in `.env.local`, no vision key, no session cookies to leak.

`aside` remains the right tool for exactly one case: a surface that requires the **owner's
own logged-in session** (a 파트너센터, an admin console). See "Owner-connected data" below.

## Tools

| tool | use |
|---|---|
| `preview_start {url}` | opens the browser pane. **Main thread only, once per run.** |
| `tabs_create {foreground:false}` | returns a `tabId` — the unit of parallelism |
| `navigate {url, tabId}` | load a URL in your tab |
| `get_page_text {tabId, max_chars}` | **first read, always.** Rendered text, cheapest |
| `javascript_tool {tabId, text}` | targeted extraction; returns JSON. Inspection only |
| `read_page {tabId, filter:"interactive"}` | `ref_N` handles when you must click or type |
| `find {tabId, query}` | locate a `ref_N` in the last `read_page` tree |
| `computer {tabId, action}` | click / type / scroll / screenshot / wait |
| `read_network_requests {tabId}` | diagnose an empty page (did the data call fire?) |
| `resize_window {tabId, preset}` | `mobile` for app-first Korean sites |
| `tabs_close {tabId}` | **always, at the end of your task** |

## Rule 1 — one tab per agent, and pass `tabId` on every single call

The browser pane is **shared across the whole session**, including every subagent. A call
that omits `tabId` hits whatever tab is active, which during a parallel run is another
agent's tab. That is how a collector silently returns a different clinic's price list.

So the contract for every spawned collector is:

```
1. tabs_create {foreground:false}     → remember the returned tabId
2. every later call carries that tabId — navigate, get_page_text, computer, all of them
3. tabs_close {tabId} before returning
```

Never call `preview_start` (main thread owns it) and never call `tabs_select` (it fronts a
tab in the user's face and belongs to the operator, not to a background collector).

### The consequence: a background tab cannot be clicked or screenshotted

Compositing only runs for the visible tab, so in a background tab
`computer {action:"left_click" | "screenshot"}` fails with **"Browser pane is currently
hidden"**. Since `tabs_select` is forbidden, a parallel collector is a **read-and-navigate**
agent, not a clicking one. Its working set is:

| works in a background tab | does not |
|---|---|
| `navigate`, `get_page_text`, `javascript_tool`, `read_page`, `find`, `resize_window`, `read_network_requests` | `computer` click / screenshot / hover / drag |

So **reach content by URL, not by clicking.** When a control looks click-only, recover the
URL it would navigate to and go there directly: read the `href` off the card or chip, or read
the framework's already-rendered state (`__NEXT_DATA__`, a Next.js RSC payload's
`initialCanonicalUrl`, a component's props) to get the id, then navigate to the normal public
page. That is reading what the page already shipped — it is **not** the same as calling a
hidden JSON API, which stays forbidden.

`computer {action:"wait"}` and `{action:"scroll"}` are the exceptions that still work, since
they need no compositing.

If a page genuinely cannot be driven without a click, that is a `gap` for the collector to
report — the main thread can then do that one page in the foreground tab, where clicking and
screenshotting work normally. Phase 2 vision reading is unaffected: it reads **downloaded
image files** with the Read tool, not screenshots.

## Rule 2 — the read ladder, cheapest first

Stop at the first rung that yields the page's real content.

1. **`get_page_text`** — rendered text. On 강남언니 this alone returned every event price.
   ⚠️ **It reads `<main>` (or `<article>`) when the page has one — so the FOOTER is invisible
   to it.** Korean business sites put the legally required 사업자등록번호·대표자·상호 in the
   footer, and a run that trusts `get_page_text` alone will report them missing. Measured
   twice on one clinic: one collector said "no 사업자등록번호 anywhere, checked footer/FAQ/
   privacy policy" and a grep of its raw agreed — both wrong, because neither ever saw the
   footer. **Pull the footer explicitly at least once per site:**
   `javascript_tool` → `document.querySelector('footer')?.innerText` (fall back to
   `document.body.innerText` when there is no `<footer>`), and **write that text to raw** so
   the claim is auditable. Never record a legal field as absent on `get_page_text` evidence
   alone.
   ⚠️ **It also returns only the summary line of a collapsed `<details>`, not the answer.**
   A native-`<details>` FAQ therefore reads as a list of questions with no answers — yet the
   answers are already in the DOM and need no clicking. Pull them with `javascript_tool`:
   `[...document.querySelectorAll('details')].map(d=>d.textContent)`. Measured: 65 Q&A pairs
   invisible to the text read, recovered whole this way.
   **The pattern behind both:** `get_page_text` is a reading convenience scoped to the main
   content region and to what is visually expanded. When a fact is *structural* — footer,
   legal block, accordion body, `<aside>`, a tab panel that is present but hidden — reach for
   `javascript_tool` before concluding the fact is not there.
2. **wait + re-read** — builder JS hydrates late. `computer {action:"wait", duration:3}`
   then read again before concluding a page is empty.
3. **scroll** — `computer {action:"scroll", scroll_direction:"down", scroll_amount:5}` in
   steps for lazy-loaded cards and infinite lists, re-reading between steps.
4. **`javascript_tool`** — targeted DOM extraction, or `scripts/extract_images.js` for image
   URLs and geometry, or `__NEXT_DATA__` for a Next.js page's typed props.
5. **`read_page` + `computer`** — only when the content needs a click (a tab, a "더보기").
6. **screenshot + vision** — the catch-all when text is baked into pixels. Same reader as
   Phase 2: `references/claude-vision-reading.md`.

`get_page_text` before `read_page`: the text read is far cheaper and answers most pages.

## Rule 3 — check robots.txt before crawling a domain, and record the verdict

Fetch `{origin}/robots.txt` once per domain. **Then find the group that applies to *you*,
which is usually not `*`.**

Under RFC 9309 the **most specific matching `User-agent` group wins, and a named group does
not inherit `*`'s rules.** Claude Browser driven by a user's request identifies as
**`Claude-User`** (and `Claude-SearchBot` for search); **`ClaudeBot` is the training crawler
and is not you.** Korean platforms increasingly allow the first while blocking the second,
so reading only the `*` group produces the opposite verdict — that mistake was made once on
this skill already.

Resolution order:

1. Is there a `Claude-User` group? → **that group alone applies.** Done.
2. Otherwise, is there another group naming this agent? → that one applies.
3. Otherwise → `*` applies — **but read step 4 before acting on it.**
4. **The intent check.** If no group names `Claude-User` **and** the file blocks the sibling
   Claude agents (`ClaudeBot`, `Claude-SearchBot`) or carries a plain-language prohibition on
   AI/RAG bot access, then falling through to a permissive `*` is reading the letter against
   the obvious intent. **Treat it as refused** and route to owner-connected data. A site that
   wanted this skill's traffic had an easy way to say so, and the sites that do want it —
   강남언니 — say so by name.

The difference is affirmative permission, not the absence of a matching string:

| pattern | verdict |
|---|---|
| `Claude-User: Allow: /` present | ✅ collect (minus that group's Disallow paths) |
| no Claude group at all, `*` permissive | ✅ collect politely |
| no `Claude-User`, but `ClaudeBot`/`Claude-SearchBot` blocked, or an "AI/RAG prohibited" notice | ⛔ do not collect — owner path |
| `*: Disallow: /` and no group names you | ⛔ do not collect — owner path |

| what the applicable group says | what you do |
|---|---|
| `Allow: /`, private paths disallowed | crawl, honour `Crawl-delay`, skip the disallowed paths |
| `Allow: /` for `Claude-User` but `Disallow: /` for `*` | **crawl** — the named group wins |
| `Disallow: /` and no group names you | **do not crawl.** Record `not-connected` with the robots quote, route to owner-connected data |
| a path you want is `Disallow`d | skip that path, collect the rest, note it as a `gap` |
| no robots.txt | crawl politely (short pause between requests, 50-page cap) |

Quote the actual applicable group in your digest, not a paraphrase — including which group
name you matched. That is what makes the verdict auditable when a policy changes.

A `Content-Signal:` header (`search=`, `ai-input=`, `ai-train=`) states **usage** rights, not
access. `ai-train=no` means the corpus must not be used to train a model; it does not forbid
collecting it to answer the operator's question.

Write the verdict into the collector's digest as a `robots` field so `report.md` can show
per-source why a platform was or was not collected. A skill that ships to other people must
be able to explain its own access decisions.

**This gate is not defeatable from inside the skill.** A `Disallow: /` is the site stating
it does not want automated agents; changing the user agent, routing through another IP, or
solving an interstitial to get around it is out of scope for this skill and for the
`org-evidence` contract it inherits. The supported answer to a blocked price is the owner,
not a workaround.

## Known browser-pane policy blocks (measured 2026-08-25)

Separate from robots: the pane itself refuses some domains outright. Plan around them, and
**never route around them with another tool.**

| domain | effect | what to do |
|---|---|---|
| every `naver.com` subdomain | "blocked by policy" | Naver is out for the run. Their robots also refuse us (no `Claude-User` group, `ClaudeBot`/`Claude-SearchBot` disallowed, explicit AI/RAG prohibition), so this is a genuine `not-connected` → owner path (스마트플레이스 관리자센터 export) |
| `google.com` (search and Maps) | **Google is the default discovery engine — try it first.** Measured failure modes: navigation denied outright in some sessions; in others the search loads but serves a **robot-check interstitial** ("비정상적인 트래픽 감지") | never solve the check — fall back to `https://duckduckgo.com/?q=…` for that query and note it. Maps may still work when search is checked; try it once and record a `gap` if not |

`scripts/fetch_naver_blog.py` predates this and will happily hit `m.blog.naver.com`. **Do not
run it while Naver is refused** — the script is not a loophole around the browser block.

## Owner-connected data — the supported path for blocked platforms

When a platform blocks automated collection, the price is not lost, because **the operator
running this skill is usually the business's owner**. Their own data is available to them
by right:

- the platform's 파트너센터 / 병원 관리자 페이지, which they are logged into — drive it with
  `aside` (their real Chrome) or have them export it;
- a CSV or screenshot of their live event list, dropped into `.scrape-out/{slug}/owner/`;
- the 원장 simply stating the current event prices.

Record these as `source: "owner-provided"` with the date. Owner-provided prices **outrank
every scraped source** in the conflict table — the owner is the authority on their own
prices, and a platform listing can be stale. For a competitor's prices there is no
owner-connected path, so a blocked platform stays a written `gap`.

## Parallel dispatch — the shape of Phase 1

The main thread opens the pane, then spawns one collector per source. Collectors run
concurrently because each owns a tab.

```
main thread:  preview_start {url: "about:blank"}     ← once
              ↓ spawn N collectors in ONE message
   ┌──────────┬──────────┬──────────┬──────────┐
   │ own-site │  Naver   │ platform │  search  │
   │ tabs_    │ tabs_    │ tabs_    │ tabs_    │   each: create → work → close
   │ create   │ create   │ create   │ create   │
   └──────────┴──────────┴──────────┴──────────┘
              ↓ each returns ONLY its digest (1–2k tokens)
main thread:  collects digests, never raw pages
```

Concurrency: **4 to 8 tabs is the working range.** Each tab is a real renderer, so more tabs
mean more memory and slower hydration for all of them; past 8 the wall-clock stops improving.

### Shard a big source across sibling agents — do not loop it in one agent

**A collector that walks N pages one after another is the run's bottleneck, and looping is
not parallelism.** Measured: one own-site collector walked 33 pages in **20.8 minutes** —
about 38 seconds per page, entirely sequential — while the other three collectors had long
since finished. The whole S1 phase cost what that single agent cost.

So when a source's page list is large, **split the list across sibling agents**, each with
its own tab:

```
scout: get the URL list first (sitemap.xml, or one nav read)   ← cheap, one agent
       ↓ split into K shards
   ┌────────────┬─────────────┬─────────────┐
   │ pages 1–11 │ pages 12–22 │ pages 23–33 │  each: tabs_create → walk → partial digest
   └────────────┴─────────────┴─────────────┘
       ↓ each returns the SAME digest schema, scoped to its slice
main:  concatenate the partials into the source's digest
```

**Shard when the list exceeds ~12 pages.** Three shards of 11 turn 21 minutes into about 7.
Rules that keep the shards honest:

- **Discover the list once, then split it.** A shard must not re-crawl the sitemap or re-walk
  the nav — hand each agent an explicit URL list, so no page is fetched twice and none falls
  out.
- **Shard by URL slice, never by topic.** "You take treatments, you take doctors" leaves the
  boundary to judgement and pages fall between the two. A numbered slice cannot.
- Counts add; `gaps` and `notable` concatenate. The main thread merges, and merging small
  typed digests is cheap.
- **Politeness is per-domain, not per-agent.** With K shards on one domain, raise each
  agent's inter-request pause so the total request rate stays where one walker would have
  been. Honour any `Crawl-delay` at the domain level.
- The 50-page cap is per **source**, not per shard — divide it across the shards.

The same applies to any per-item write loop downstream. Measured: 43 entity inserts took
**17.6 minutes** in one agent, ~25 seconds each; sharded four ways that is about 5.

The per-agent task spec is the four-field contract from `SKILL.md` — objective, output
format, sources and tools, boundaries — plus these three lines, verbatim:

> Open your own tab with `tabs_create {foreground:false}` and pass its `tabId` to every
> browser call. Close it before returning. Do not call `preview_start` or `tabs_select`.
> Check `{origin}/robots.txt` first and record the verdict in your digest's `robots` field.

## Failure handling

| symptom | reading | move |
|---|---|---|
| `navOk:true`, text is a cookie/app-download shell | not hydrated yet | wait 3s, re-read; then `resize_window {preset:"mobile"}` and reload |
| text present, `javascript_tool` sees an empty body | whole-site iframe | use `get_page_text` (frame-aware) + per-section screenshots — `dynamic-capture.md` §4b |
| a URL param is ignored (SSR sees it, client renders empty) | client-only router state | drive the site's own UI instead; if that fails, record a `gap`. Do not call the internal JSON API the page uses |
| 403 / challenge page / login wall | the site is refusing an automated agent | `access-failed` + robots quote → owner-connected path. No retry loop |
| **the browser tool itself refuses the domain ("blocked by policy")** | a harness-level policy block, *not* a robots question | **stop for that domain.** Record `not-connected` (reason: tool policy) and route to owner-connected data. **Do NOT retry the same domain through `aside`, the `agent-browser` CLI, `curl`, or a subagent** — switching tools to reach a domain the harness blocked defeats the block, and the fallback ladder in this file never authorises that. Reading `{origin}/robots.txt` to record the verdict is fine; fetching content is not |
| tab unresponsive | stale handle | `tabs_close`, `tabs_create`, retry once. Two attempts maximum |
| **a list renders zero rows, but the page's own counter says there are results** | a **virtualized list** measuring a 0×0 viewport, because the tab is hidden | **nudge layout, do not conclude "not listed".** `resize_window` (e.g. to `mobile` then back, or any explicit width/height) fires a resize the virtualizer listens for; then re-read. Same root cause as the missing IntersectionObserver in infinite scroll |

⚠️ **The 0-rows case produced a measured false negative.** One run recorded a clinic as
`available-but-empty` on 여신티켓 — "genuinely not listed" — and even ran a control test with
a different clinic name to confirm. The control failed the same way, so it confirmed nothing.
The clinic *was* listed; its merchant had simply paused its events. **A control test run in the
same hidden tab cannot distinguish absence from a rendering artifact.** Before writing
`available-but-empty`, nudge the layout, check the page's own count fields (`salesEventCount`,
`event_count`, a results-count label) in the SSR payload, and only then call it absence.

Measured example of row 3: `gangnamunni.com/search?keyword=<clinic-name>` returns HTTP 200 and
`__NEXT_DATA__.query.keyword` holds the term, but the rendered page says `''에 대한 검색결과`
and never fires a search request. The desktop web search is not drivable by URL — which is
a `gap`, not an invitation to call `/api/solar/search/...` directly.
