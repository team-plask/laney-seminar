# Corpus contract: what a scrape run produces

Shared contract, the seam in the pipeline. The scraping runbook (`scraping.md`) WRITES these artifacts;
`entity-setup` READS them and may not go looking at anything else.

Every run writes to `.scrape-out/{slug}/` (repo root, gitignored). Four artifacts,
in dependency order: `manifest.json` ← `raw.json` ← `content-graph.json` ← `report.md`.
**v2 note:** the librarian's `corpus-index.json` = this file's `content-graph.json` shape
PLUS an `inventory`/`conflicts`/`missing` header (see SKILL S2) — same collections, same
refs; the Architect plans from it and every site-plan ref must resolve against it.
Nothing is written to any database — these files are the whole output, and the
`entity-setup` skill consumes them.

**Provenance is non-negotiable.** Every collected fact carries `sources[]` saying which
page or image it came from. A fact with no source is a fabrication — don't write it.

**Layer boundary (why there is no `sections`/`slogan` here).** A landing DAG has two
layers: the DATA-relationship layer (what exists and what links to what — only knowable at
scrape time) and the LANDING-DESIGN layer (slogan copy, section layout, tone/align rhythm,
hero/nav choices — pure design judgement). This skill owns ONLY the data layer and stops at
`content-graph.json`. **All landing design is `entity-setup`'s job**, so those rules live in
one place, not two. Do not write slogans, sections, or tone here.

```
.scrape-out/{slug}/
├── raw.json            # schema-neutral collected data (facts + provenance)
├── images/{category}/… # downloaded originals
├── manifest.json       # image inventory (written/merged by download_images.py)
├── readings/           # per-image reading results (JSON, one per read image)
├── content-graph.json  # DATA layer: entities/products/promotions + relations + image matches
└── report.md           # human summary — coverage, conflicts, unresolved items
```

## `raw.json`

```jsonc
{
  "meta": {
    "slug": "abijou",                  // filesystem-safe org handle
    "industry": "hospital",            // hospital | law | tax
    "input": "https://…",              // what the user gave us
    "scraped_at": "2026-07-24T…",
    "sources_attempted": [             // one per research agent
      { "platform": "own-site", "ok": true, "pages": 14 },
      { "platform": "gangnamunni", "ok": false, "error": "login wall" }
    ]
  },

  "org": {
    "name_ko": "…", "name_en": "…",
    "address": "…", "phone": "…", "hours": "…",
    "homepage": "https://…", "sns": { "instagram": "…", "blog": "…" }
  },

  // Korean legal footer info — MANDATORY collection target (footer_config needs it).
  // If genuinely absent, keep the keys with null and list it in report.md unresolved.
  "legal": {
    "representative": "…",
    "business_registration_no": "…",
    "phone": "…",
    "sources": [ { "type": "page", "url": "…#footer" } ]
  },

  "brand": {
    "logo_candidates": [ { "manifest_id": "…", "kind": "icon|wordmark|favicon" } ],
    "colors": { "primary_candidates": ["rgb(…)"], "accents": [], "footer_bg": "…" }
  },

  "collections": {
    // Industry vocabulary maps onto these fixed keys — see industry-profiles.md.
    // hospital: offerings=시술, people=의료진 · law: offerings=업무분야, people=변호사, …
    // An offering is BOTH a content node (entity) AND a commerce row (product) in
    // this repo — they are separate tables joined by product.entity_id. Collect both
    // sides here; the content graph splits them into an entity + a product.
    //   • content side → name/category/description/duration (→ entity)
    //   • commerce side → `commerce{}` (→ product row). null when the org hides prices.
    // Do NOT invent a price — 청담 프리미엄 병원은 가격 비공개가 정상이다.
    "offerings": [{
      "id": "off-lifting",                     // stable slug-style id, referenced elsewhere
      "name": "울쎄라 리프팅",                   // canonical (own-site naming wins)
      "aliases": ["울세라"],                    // other platforms' names for the same thing
      "category": "리프팅",
      "duration": "30분",
      "description": "…",
      // The `products` row this maps to. null ⇒ no commerce data found (content-only entity).
      "commerce": {
        "price": 590000,                       // 정가(regular), VAT 관례는 출처 기록. null 가능
        "sale_price": null,                    // 상시 할인가(정가보다 낮을 때만). 이벤트 특가는 promotions로
        "currency": "KRW",
        "inventory": null,                     // 병원 시술엔 대개 무의미 → null
        "status": "active",                    // active | draft | archived
        "unit_note": "300샷 기준"               // 가격 단위/조건 메모
      },
      "sources": [ /* source objects, see below */ ]
    }],
    "people":   [{ "id": "p-kim", "name": "…", "title": "대표원장",
                   "roles": ["리프팅", "보톡스"],       // 담당시술 | 전문분야
                   "career": ["…"], "credentials": ["…"],
                   "photo": "manifest_id|null", "sources": [] }],
    "cases":    [{ "id": "c-1", "kind": "success-case|before-after|review",
                   "title": "…", "summary": "…", "result": "…",
                   "related_offering": "off-…|null", "date": "…", "sources": [] }],
    "press":    [{ "title": "…", "outlet": "…", "date": "…", "url": "…",
                   "summary": "…", "sources": [] }],
    // Maps to the repo's `promotions` table — NOT a product. An event/sale is a
    // dated RULE that derives a discounted price; the regular price stays on the
    // offering's commerce{}. This is deliberate (the repo forbids event-as-product).
    "promotions": [{
      "id": "promo-2026bigsale",
      "kind": "event",                         // event(자동적용) | coupon(코드) | benefit(조건부 혜택)
      "name": "2026 아비쥬 빅세일",
      "benefit_type": "percent",               // price(고정 이벤트가) | percent(%할인) | amount_off(원 할인) | gift(사은품)
      "value": 15,                             // benefit_type에 따라: percent=15, price=290000, amount_off=100000, gift=0
      "starts_at": "2026-07-20", "ends_at": "2026-08-01",   // 기간(YYYY-MM-DD). 상시면 ""
      "code": null,                            // coupon일 때만
      "condition": "1인 1회 한정",              // benefit/조건부일 때 산문으로
      "target": { "kind": "offering|org-wide", "offering_id": "off-…|null" },  // entity/product 타겟 or org 전체
      "image": "manifest_id|null",             // 이벤트 배너 (이미지 판독 대상이기도)
      "sources": [] }],
    "faqs":     [{ "q": "…", "a": "…", "sources": [] }],

    // 조직 OWN 공식 블로그의 글 전체 (fetch_naver_blog.py 산출물에서).
    // 제3자 후기 블로그는 여기 넣지 않는다 — 사실만 추출해 다른 컬렉션에 병합.
    "posts":    [{ "id": "post-224354675794", "title": "…", "date": "…",
                   "url": "https://blog.naver.com/{blogId}/{logNo}",
                   "text": "본문 전체(플레인)",       // 원문은 naver_blog/{blogId}/posts.json에도 보존
                   "md": "본문 **마크다운** — 제목/굵기/인용/이미지 위치를 구조 그대로",
                   //  ↑ 목표 포맷: fetch_naver_blog.py가 SmartEditor 컴포넌트를 md로 변환
                   //    (헤딩→#, 인용→>, 이미지→![](이미지URL) 본문 내 위치 유지).
                   //    md가 있으면 text보다 md를 정본으로 쓴다(발췌·관련글 밴드·추후 자체
                   //    포스트 페이지의 원천). 구버전 수집물은 text만 있을 수 있음.
                   "images": ["manifest_id…"],       // 다운로드된 경우 manifest 참조
                   "topics": ["off-lifting"],        // 관련 offering id 매칭 (컴파일 단계)
                   "sources": [] }],

    // 발견 데이터(자유도): 위 표준 컬렉션에 안 맞는데 사이트가 실제로 가진 콘텐츠는
    // 버리지 말고 여기에. 병합 스킬의 핵심 취지 — AI가 읽은 걸 랜딩까지 잇는다.
    // 예: 법무 뉴스레터/칼럼, 세무 절세리포트, 병원 프로그램/멤버십, 장비 상세.
    // 각 그룹은 자유 형태지만 최소 {label, items[]}는 갖춘다. 빌드 단계에서
    // 그룹 루트+자식+섹션으로 승격된다 (S3 계획, entity-dag.md §7).
    "extra": [{
      "key": "columns",                    // 슬러그로 쓸 안정 키
      "label": "칼럼",                      // 표시명 (섹션 헤딩 후보)
      "kind": "articles|programs|gallery|list|stats|reviews",  // 힌트(섹션 형태 결정용)
      "items": [{ "title": "…", "text": "…", "url": "…", "images": ["manifest_id…"], "sources": [] }]
    }]
  }
}
```

**Source object** (the provenance unit, used everywhere):

```jsonc
{ "type": "page",  "platform": "own-site|naver|gangnamunni|yeoshin|babytalk|google|lawtalk|news", "url": "…" }
{ "type": "image", "platform": "own-site", "url": "…", "manifest_id": "…" }   // fact read FROM an image
```

Conflict rules when merging platforms: canonical `name` = own-site's naming; price =
가장 구체적인 출처 우선 (hospital: gangnamunni > own-site > others). Record losers in
`aliases` / keep both prices only when they describe different packages.

## `manifest.json` (owned by `download_images.py`)

Array of image entries:

```jsonc
{
  "id": "a1b2c3d4",                    // content-hash prefix — the manifest_id others reference
  "src": "https://…", "aliases": [],  // duplicate URLs resolved to this entry
  "local": "images/people/a1b2c3d4_kim.jpg",
  "category": "people|offering|facility|event|logo|hero|uncategorized",
  "width": 1200, "height": 800, "bytes": 152340, "sha256": "…",
  "page": "https://…",                 // where it was found
  "alt": "…",
  "matched_entity": "p-kim|off-lifting|null",   // filled during compile phase
  "reading": { "status": "pending|done|skipped", "result": "readings/a1b2c3d4.json" },
  "thumbnail_candidate": true          // own-site photo, min(w,h) ≥ 400 — see policy below
}
```

**Thumbnail policy:** only own-site images become `thumbnail_candidate`. Platform images
(강남언니 etc.) are data sources, never reusable assets — copyright.

## `readings/{manifest_id}.json` (image reading results)

Whatever a text-bearing image yielded, structured:

```jsonc
{ "manifest_id": "…", "read_by": "claude|gemini",
  "kind": "event-banner|price-table|page-image|other",
  "extracted": { /* kind-specific: promotion {name, period, benefit_type, value, condition} · price rows {offering, price} · free text */ },
  "merged_into": ["promotions[2]", "offerings[5].commerce.price"] }   // where it landed in raw.json
```

## `content-graph.json`

The **DATA layer** of this repo's model — the entities/products/promotions and how they
relate, resolved to the extent only a scrape can (image↔entity matches, offering↔product↔
promotion links, category grouping). It is **NOT a landing page**: no slogans, no sections,
no tone. `entity-setup` reads this graph and BUILDS the landing (writes slogans, arranges
sections) on top of it — that design layer lives there, in one place.

Field names track the impl files (`entity.ts` / `product.ts` / `promotion.ts`); see
`skills/entity-setup/references/data-model.md`. Keys are temporary handles — uuid
minting, image upload, `loc`/slogan authoring, and INSERTs are all `entity-setup`'s job.

**The offering split (critical):** each `offerings[]` item becomes TWO rows — a content
`entity` (name + factual description + matched image) AND a `products` row (commerce:
price/inventory/status) linked by `entity_key`. A promotion becomes a `promotions` row
targeting that entity/product, NEVER its own product/entity.

**What this skill DOES fill:** the factual `description` (localized, straight from the
source — NOT a marketing slogan), the matched `image`, the `category`/parent grouping, and
every cross-link. **What it leaves for entity-setup:** `slogan` (heading copy), `sections`,
tone/align/layout, hero/nav choices. Those are absent here by design.

```jsonc
{
  "entities": [{
    "key": "f-lifting",                        // temp handle, unique in this file
    "role": "offering|person|case|group|org",  // what this node is (drives grouping)
    "name": "울쎄라 리프팅",                    // canonical name (own-site wins)
    "description": { "ko": "…", "en": "…" },   // FACTUAL description from source — not a slogan
    "category": "리프팅",                       // for grouping under a parent
    "image": { "manifest_id": "…", "local": "images/…" },  // matched crawl photo
    "needs_generation": false,                 // true ⇒ no usable crawl image found
    "source": "off-lifting"                    // back-ref into raw.json for provenance
  }],

  // Relationships (repo: entity_edges) — the graph is a DAG (a node may have many parents).
  // Grouping + associations discovered at scrape time: which offerings sit under which
  // category, which case/post relates to which offering, which doctor handles what.
  "edges": [{ "parent": "grp-lifting", "child": "f-lifting", "relation": "member", "position": 0 }],

  // Commerce rows (repo: products). One per offering WITH commerce data. entity_key links
  // to the content entity (products.entity_id). From offerings[].commerce.
  "products": [{ "key": "prod-lifting", "entity_key": "f-lifting",
                 "name": "울쎄라 리프팅 300샷", "status": "active",
                 "price": 590000, "sale_price": null, "inventory": 0,
                 "source": "off-lifting" }],

  // Dated pricing RULES (repo: promotions). Target an entity/product, or org-wide.
  // Regular price stays on the product; this only derives the discount. Never a product.
  "promotions": [{ "key": "promo-bigsale", "kind": "event",
                   "name": "2026 빅세일", "benefit_type": "percent", "value": 15,
                   "starts_at": "2026-07-20", "ends_at": "2026-08-01",
                   "code": null, "condition": "",
                   "target": { "entity_key": "f-lifting" },   // or {"product_key": …} or {} for org-wide
                   "source": "promo-2026bigsale" }],

  "notes": [ "매칭 근거·미해결 관계·모호했던 그룹핑 — entity-setup이 읽을 자유 텍스트" ]
}
```

`entity-setup` applies its own phase-2/3 rules (slogan voice, line budgets,
card-needs-image, tone/align rhythm, section composition) on top of this graph. This skill
must NOT pre-empt those — ship facts and relations, not design.

## `report.md`

Human-readable run summary, in this order:

1. **한 줄 요약** — org, 업종, 수집 규모
2. **소스별 결과 표** — platform | ok/실패 | 수집 항목 수 | 비고(로그인 벽 등)
3. **컬렉션 카운트** — offerings N (가격있음 M) / people N / cases N / press N / promotions N / faqs N / posts N
4. **이미지 통계** — 다운로드 N (카테고리별), 판독 N건 → 병합된 사실 N개, 썸네일 후보 N / needs_generation N
5. **충돌 해소 내역** — 이름/가격이 플랫폼 간 달랐던 항목과 채택 근거
6. **미해결 항목** — 누락 법정 정보, 매칭 실패 이미지, 접근 실패 소스 등 후속 조치 목록
