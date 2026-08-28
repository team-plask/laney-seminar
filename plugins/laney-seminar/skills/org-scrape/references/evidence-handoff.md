# Evidence handoff: corpus → org-evidence ledger

`org-scrape` ends at `corpus-index.json`. `org-evidence` owns the Markdown evidence ledger
that `org-launch-prep` and `org-presence-audit` read. This file is the mapping between the
two, so that a corpus never has to be re-collected to become evidence, and so that nothing
reaches the ledger without a source, an observation time, and a state.

The ledger shape itself is defined by `org-evidence` (`references/evidence-ledger.md` in
that skill). This file only says which corpus field fills which ledger slot.

## Source coverage

Every collector in `industry-profiles.md` ends as one row of the ledger's source-coverage
table. Map the corpus outcome to the `org-evidence` state vocabulary:

| corpus outcome | ledger state | notes |
|---|---|---|
| digest present, items > 0 | `connected` | public HTTP/browser sources count as connected once observed |
| digest present, items = 0 | `available-but-empty` | the source exists and was read; nothing relevant there |
| roster excludes the source for this industry | `not-applicable` | e.g. 강남언니 for a law firm |
| `gap` with a login wall, WAF, 403, empty shell | `access-failed` | keep the literal error; never re-describe blocked as absent |
| a useful owner-managed source Laney is not connected to | `not-connected` | SmartPlace export, GBP, Search Console |

The locator column is the corpus ref plus the `raw/` path. The observed column is the
digest's fetch time. A `gap` marked `retryable` stays `access-failed` until a later run
succeeds; it never silently becomes `connected` by being carried forward.

## Evidence entries `[E-*]`

One `[E-*]` entry per raw page or reading that a claim will cite:

| ledger field | corpus source |
|---|---|
| locator | the page URL, or the image URL for a vision reading |
| observed | the fetch time recorded in the digest |
| status / hash | HTTP status and the content hash from `raw/` when the collector recorded one |
| excerpt | the digest's notable fact, not the raw page |
| rendered path / locale | `dynamic-capture.md` records these for scrolled or clicked states |

Keep the raw page on disk under `.scrape-out/{slug}/raw/`; the ledger cites it, it does
not copy it. A vision reading (`readings/`) is evidence for the image it read, with the
image URL as locator and the reading time as observed.

## Claims `[C-*]`

Each typed corpus item becomes one atomic claim, split the way
`identity-and-conflicts.md` in `org-evidence` requires:

| corpus collection | atomic claims |
|---|---|
| `offerings` | one claim per offering name; a separate claim for its price, its promotion interval, its duration |
| `people` | one claim per professional for role; a separate claim per credential |
| `events` | one claim per event with an explicit effective interval |
| `facility` / contact fields | address, phone, hours, and dated exceptions as separate claims |
| `press`, `posts` | historical claims with the article/post date as the effective time |

Every claim cites the `[E-*]` entries behind it. A price read from an image cites the
image's entry, not the page that embedded it.

## Conflicts

`corpus-index.json` carries a `conflicts` array. Do not resolve it here. Each entry becomes
an `[X-*]` line in the ledger with both observations preserved. `org-launch-prep` decides,
using source authority for that predicate and the effective interval; majority vote is not
a method. Medical, legal, credential, price, and tax conflicts are a hard gate for
`org-launch-prep`, so surface them prominently in `report.md`.

## Assets `[A-*]`

`corpus-index.json` image refs become `[A-*]` lines with rights set from the collector:

- images from the organization's own site or official blog: `published-only` until the
  owner grants reuse; a thumbnail candidate is still not a licensed asset
- images from third-party blogs, review platforms, or news: `third-party`; data extraction
  only, never reuse
- vision readings are evidence about the image, not a right to the image

## Two decisions that gate depth

These are recorded here because the playbooks predate the `org-evidence` contract and the
contract wins. Each has a compliant default; the alternative needs an explicit owner
decision written into the run's `report.md`.

1. **Naver blog private endpoint.** `scripts/fetch_naver_blog.py` lists posts through the
   undocumented `m.blog.naver.com/api/.../post-list` endpoint. `org-evidence`'s source
   routing forbids undocumented private endpoints. Compliant default: the RSS feed
   (`rss.blog.naver.com/{blogId}.xml`) and server-rendered mobile post pages, which cover
   recent posts; record older posts as `not-connected` (owner-managed export needed). The
   private endpoint is used only when the owner has authorized full-blog collection and the
   decision is recorded.
2. **Forced checklist versus minimum collection.** `industry-profiles.md` forces a full
   roster because a fact absent from the corpus cannot reach a page. `org-evidence` asks for
   the minimum evidence the task needs. Resolution: purpose decides. Launch preparation
   runs the forced checklist. A presence audit does not activate this skill unless a
   rendered surface is material to a finding, and then only for that surface.
