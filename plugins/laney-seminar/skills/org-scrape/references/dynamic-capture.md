# Capturing dynamic content — banners, sliders, builder pages

Korean clinic/firm sites are built on page builders (imweb, 카페24, Wix, Cafe24)
whose real content — event banners with prices, hero images, promotion cards — is
NOT plain `<img>` in the initial HTML. A naive `get text` + `img[]` scrape misses
exactly the pages that matter (the /PM promotion page: it showed "리쥬란 원데이
올인원 59만원" to a human but the first scrape returned old 2020 thumbnails).

This file is the playbook for getting that content. Techniques are ordered from
cheapest to most robust; escalate until the page yields.

## Rule 0 — always use the rendered DOM, never raw HTML

Fetch through the browser (agent-browser), never `curl` the HTML, for any JS site.
Builder pages ship a near-empty shell and hydrate client-side (this is why
WebFetch/WebSearch are banned in this skill). This is the same reason Firecrawl and
similar tools render in a headless browser before extracting — raw HTML is a shell.

## 1. Render timing — wait, then re-read

Builder JS hydrates seconds after load. Never trust the first read.

```bash
agent-browser --session s open <url>
agent-browser --session s wait --load networkidle
agent-browser --session s wait 4000          # let the builder module hydrate
```

If `get text` is sparse or `img[]` looks wrong on the first pass, wait and re-extract
before concluding the page is empty. (The /PM miss was a single-read conclusion.)

## 2. Scroll to trigger lazy-load

Cards and images below the fold load on scroll. Scroll in steps with a wait each:

```bash
for i in 1 2 3 4; do
  agent-browser --session s scroll down 1500
  agent-browser --session s wait 1200
done
```

`extract_images.js` already resolves `data-src` / `data-original` / `data-lazy`
placeholders, but the element must be scrolled into view first to swap its real src.

## 3. CSS background-images (the imweb/builder banner case)

Builder banners are a DIV with a `background-image` set via a CSS **class**, text
overlaid — not an `<img>`. `extract_images.js` now scans **computed** style on every
element (size-filtered ≥200×120) and returns them in `backgroundImages[]` with the
overlaid `context` text. On /PM this went from 0 → 26 captured. Merge
`backgroundImages` into the Phase-2 download list (category `event`/`hero`) so they
get downloaded and read, same as `<img>`.

## 4. Sliders / carousels

Swiper/slick and friends keep all slides in the DOM but translate the inactive ones
off-screen — so query **all** slides, not the visible one:

```js
document.querySelectorAll('.swiper-slide, .slick-slide, [class*="carousel"] li')
```

If slides are truly virtualized (only the active one in the DOM), advance the
carousel and re-extract between clicks:

```bash
agent-browser --session s find text "다음" click   # or click the next-arrow ref
agent-browser --session s wait 800
```

## 4b. Codelet / whole-site iframe embeds (the hardest SPA case)

Some builders (e.g. noalaw.co.kr) render the **entire site inside one iframe** —
`src=".../_assets/remote/embed/codelet/<id>/index.html"`. Symptoms:
- `eval` on the top document sees NOTHING (`document.body.innerText.length === 0`,
  `querySelectorAll('img')` empty) — so `extract_images.js` returns all zeros.
- The iframe is flagged **cross-origin** (contentDocument blocked) even on the same
  domain, so you can't reach into it with JS.
- Opening the iframe `src` as its own page **doesn't hydrate** — the codelet renders
  only inside its parent (standalone gives a near-empty ~200-char shell).

What DOES work:
- **`get text body`** — agent-browser's text read is **frame-aware** and traverses
  into the iframe, returning the full rendered text (85K chars on noalaw where eval
  saw 0). Use `get text` for the copy even when `eval` extraction is blocked; parse
  collections from it.
- **Per-section navigation + screenshot** — nav items are JS buttons (no hrefs), so
  click each menu item (`find text "업무분야" click`) and screenshot each view, then
  read the screenshots with vision. This is the only path to the images/structure.
- ⚠️ **`screenshot --full` captures only the hero** here — the iframe has a FIXED
  height, so the parent's scroll height never grows and "full page" is just the first
  viewport. Screenshot **per section after navigating/scrolling inside the iframe**,
  not one --full of the parent.

Detect this case early: if `get text` returns lots of text but `eval` reports
`document.body.innerText.length === 0`, you're in a whole-site iframe — switch to the
get-text + per-section-screenshot strategy immediately instead of fighting `eval`.

## 5. iframes

Builder widgets and social embeds live in iframes. `extract_images.js` runs in the
top document and cannot see into them. Handle by origin:

- **Same-origin iframe** → its content is reachable; read `iframe.contentDocument`
  inside an `eval`, or open the iframe's `src` as its own page and extract there.
- **Cross-origin iframe** (Instagram feed, YouTube) → JS can't reach in. Open the
  `src` URL directly as a page if it's content you need; otherwise ignore (usually
  a social embed, not org data).

Enumerate first: `eval "[...document.querySelectorAll('iframe')].map(f=>({src:f.src,w:f.offsetWidth}))"`.
(On /PM the two iframes were a 1×1 tracker and a hidden social embed — neither held
the banners, which were background-images. Always check before assuming.)

## 6. Baked-in text → screenshot + vision (the robust catch-all)

The hard case: the price/event text is **designed into the banner graphic** (pixels,
not HTML). No DOM technique can read it — `context` is empty because there IS no text
node. This is 청담아리움's 59만원 banner. Two moves, and the second is the safety net
for ANY page this playbook can't crack:

1. **Capture the banner image** (via §3) → run `read_images.py`; the vision model
   OCRs the baked-in "59만원 / 7.10-8.31" into `prices` / `promotion`.
2. **Full-page screenshot → vision**, when `get text` is sparse but the page is
   visually rich (`pageSignals.imageHeavy`, or a builder page that resisted §1–5):

   ```bash
   agent-browser --session s screenshot /tmp/{slug}_{page}.png --full
   ```
   Then read that screenshot the same way `read_images.py` reads any image — the
   vision model returns the events/prices/structure a human sees. This is exactly
   how the 59만원 event was confirmed, and it is what Firecrawl-style "screenshot +
   LLM extract" modes do for JS-heavy pages. It costs one vision call per page but
   never returns a false "empty page".

**Escalation order:** §1 wait → §2 scroll → §3–5 DOM extraction → §6 screenshot+vision.
Stop at the first that yields the page's real content. For a known builder promotion
page, jumping straight to §6 (screenshot the whole page, read it) is often the fastest
reliable path.

## Reading criteria (why we read almost everything)

`download_images.py` marks every downloaded image `reading: pending` except logos/
favicons — it does **not** gate on the crawler's `category` guess (event banners have
arrived mis-tagged "homepage" and been skipped). The vision reader's `image_class` is
the real router; reading a decorative image just labels it, cheaply and in parallel.
Trusting the category guess is what silently dropped the one banner with the price.
