# Platform strategies — where each fact lives, per source

Per-source playbooks for the research agents. Industry assignment of agents is in
`industry-profiles.md`; this file is the per-platform "what to extract and how".

## Own website (모든 업종 — 가장 권위 있는 소스)

Best source for: 공식 명칭(canonical), 상세 설명, 인물 프로필 전체, 브랜드 자산(로고/컬러),
법정 사업자 정보(푸터), 전 이미지.

**Crawl pattern** (Claude Browser — 자기 탭에서, `tabId` 매 호출 전달):
1. 메인 페이지 → `read_page {filter:"interactive"}`로 네비 구조 파악
2. 네비의 콘텐츠 페이지 전부 방문 (시술/업무분야, 인물, 사례, 소개, 오시는길)
3. 페이지마다: `navigate` → `get_page_text` → 비면 `computer {action:"wait"}` 후 재독 →
   `computer {action:"scroll"}`(lazy-load) → `javascript_tool`로 `scripts/extract_images.js`
4. `pageSignals.imageHeavy == true`인 페이지는 **이미지 페이지로 플래그** — 텍스트 수집을
   포기하지 말고 이미지 전부를 판독 대상(reading: pending)으로 마킹
5. 푸터에서 legal 3종(대표자/사업자등록번호/전화) — 필수

> ⚡ **카탈로그 페이지를 먼저 찾아라. 그 한 장이 상세 N장을 대체한다.**
> 많은 병원 사이트에 `/procedures`류의 **전체 시술 목록 페이지**가 있고, 거기에 이름·태그라인·
> 시작가가 한꺼번에 있다(실측: 한 피부과의 `/ko/procedures` 한 장에 43개 시술 전량). 상세 페이지는
> 설명을 두껍게 해줄 뿐 **목록을 늘리지 않는다.**
> 순서: ① 카탈로그 1장으로 전 항목의 이름·가격을 확보 → ② 상세는 **주력 10~15개만**.
> 상세 1장이 평균 38초다. 43개를 전부 돌면 27분, 상위 15개만 돌면 10분이고 카탈로그 커버리지는
> 동일하다. 어떤 상세를 건너뛰었는지는 `notable`에 적어 downstream이 얇은 카피의 이유를 알게 한다.
> `seminar` 프로파일에서는 상위 N개 제한이 기본이고, `launch`에서는 전 상세를 돈다.

> ⚠️ **홈페이지의 목록은 큐레이션된 top-N이다. 개수를 믿지 말고 전용 페이지로 따라가라.**
> 실측(한 피부과): 홈페이지 "인기 시술" 탭이 카테고리별 건수를 `8월 이벤트 10`으로 표시했지만,
> `/ko/event/month-event` 전용 페이지에 실제로는 **26건**이 있었다. 나머지 4개 카테고리는
> 일치. 홈페이지 시드만 믿었으면 41건으로 끝났을 것을 실제로는 **57건**이 나왔다.
> **탭 배지의 숫자는 시드이지 전수가 아니다** — 각 카테고리의 `href`를 따라가 전용 페이지에서
> 세고, 가능하면 DOM의 안정적인 항목 마커(예: 장바구니 폼의 `procedure_id` 개수)로 교차검증하라.

> ⚠️ **"EVENT" 배지가 곧 할인은 아니다.** 같은 실측에서 카드마다 가격이 **하나뿐이고**
> `<del>`·`.line-through` 같은 정가 표기가 DOM에 아예 없었다. 사이트 자체 마스터 카탈로그
> (`/ko/procedures`의 "시작가")와 대조하니 EVENT 배지가 붙은 여러 항목이 비이벤트 시작가와
> **동일 가격**이었다. 따라서 `regular_price`·`discount_pct`를 **추정해서 채우지 말 것** —
> 없으면 `null`로 두고, 배지와 실제 할인의 불일치는 `notable`에 기록해 downstream이 "할인"으로
> 카피를 쓰지 않게 한다. 정가가 필요하면 소유자에게 확인하는 게 정답이다.

## Naver (모든 업종) — ⛔ 2026-08-25 현재 자동 수집 불가, 소유자 경로로

> **이 절의 수집 지침은 robots 게이트를 통과한 뒤에만 유효하다. 현재는 통과하지 못한다.**
> 실측(2026-08-25):
>
> | 도메인 | 우리에게 적용되는 그룹 | 판정 |
> |---|---|---|
> | `blog.naver.com` / `m.blog.naver.com` | **`Claude-User` 그룹 없음.** `ClaudeBot: Disallow: /`, `Claude-SearchBot: Disallow: /` 명시. 상단에 *"BOT ACCESS FOR THE PURPOSES OF AI TRAINING AND RETRIEVAL-AUGMENTED GENERATION (RAG) IS STRICTLY PROHIBITED"* | ⛔ **수집 금지** |
> | `search.naver.com` | `*: Disallow: /` | ⛔ |
> | `rss.blog.naver.com` | `*: Disallow: /` ("Block everything for every crawler") | ⛔ |
> | `map.naver.com` | `*: Disallow: /` (일부 경로만 Allow) | ⛔ |
>
> 강남언니와 **정반대 케이스**임에 주의하라. 강남언니는 `Claude-User`를 이름으로 허용했고,
> 네이버는 아는 Claude 에이전트를 전부 차단한 뒤 목적(RAG) 자체를 금지한다고 문장으로 썼다.
> `blog.naver.com`의 `*` 그룹이 일부 `.nhn` 경로만 막는다고 해서 그리로 우회하지 말 것 —
> `claude-browser.md` Rule 3의 **의도 확인(step 4)**에 걸린다.
>
> ⚠️ **Claude Browser는 naver.com 전 서브도메인을 "blocked by policy"로 거부한다.** 이는
> robots 문제가 아니라 하네스 정책 차단이므로, `aside`·`agent-browser`·`curl`·서브에이전트로
> **갈아타 우회하지 말 것.** 한 번 그런 폴백이 발생했고(실측), 그게 이 경고가 생긴 이유다.
>
> **정답은 소유자 경로다** — 원장님의 **스마트플레이스 관리자센터** 내보내기, 블로그 관리자
> 백업, 또는 원장님이 직접 제공하는 자료. `source: "owner-provided"`로 기록한다.
> 소유자 자료가 없으면 Place/블로그는 `not-connected`(사유: robots + 도구 정책)로 남긴다.

<details>
<summary>참고 — robots가 허용으로 바뀌거나 소유자 경로로 동일 데이터를 받았을 때의 필드 지도</summary>

- **통합검색** `search.naver.com/search.naver?query={상호}` — 공식 사이트 링크, Place 진입점
- **Naver Place** — 영업시간·주소·전화의 1순위 소스, 등록 메뉴/가격, 방문자 리뷰,
  **공식 블로그 링크** (블로그 파이프라인의 blogId 발견 경로)
- **블로그 검색** `?where=blog&query={상호} 시술` (hospital) — 사이트에 없는 시술명 보충
- **뉴스 탭** `?where=news&query="{상호}"` (law/tax **필수**) — press 컬렉션의 주 소스:
  제목/매체/날짜/링크. 동명 조직 주의 — 지역·대표자명으로 교차 확인

> ⚠️ **네이버 결과 링크는 셀렉터로 안 잡힌다.** 검색 결과 앵커의 href가 클릭
> 추적 리다이렉트로 감싸여 있어 `a[href*=blog.naver]` 류 셀렉터가 0건을 반환한다
> (실측). **`get text body`로 결과 영역 텍스트를 받아 제목·매체·날짜를 파싱**하는
> 방식을 병행하라. 셀렉터만 믿지 말 것.
> ⚠️ **동명 로펌/병원 오귀속 주의.** `blog.naver.com/lawoffice_noah`(LAW NOAH)와
> `noalaw.co.kr`(법률사무소 노아)는 완전히 다른 로펌이다. 블로그/뉴스를 org에
> 귀속시키기 전에 대표자·주소·업무분야로 동일 조직인지 반드시 확인 — 불일치면 제외.

### Naver 블로그 — 브라우저 없이 HTTP로 전량 수집 (실측 검증됨)

> **org-evidence 계약 우선.** 아래의 `post-list` JSON 엔드포인트는 문서화되지 않은 비공개
> 엔드포인트라 `org-evidence` source-routing이 금지한다. 기본은 RSS(`rss.blog.naver.com`) +
> 서버렌더 모바일 본문 페이지이며, 이 경우 최근 글만 수집되고 그 이전 글은 `not-connected`
> (소유자 내보내기 필요)로 기록한다. 비공개 엔드포인트는 소유자가 전량 수집을 승인해
> `report.md`에 기록한 경우에만 사용한다. 근거: `references/evidence-handoff.md`.

PC 버전(blog.naver.com)은 본문이 iframe(`mainFrame` → PostView.naver) 안에 있어 크롤러의
고전적 함정이고, headless 브라우저는 로드가 자주 실패한다. **모바일 버전을 curl 수준
HTTP로 수집하는 것이 정답이다** — 브라우저 불필요:

1. **글 목록**: `https://m.blog.naver.com/api/blogs/{blogId}/post-list?categoryNo=0&itemCount=30&page={N}`
   — **`Referer: https://m.blog.naver.com/{blogId}` 헤더 필수** (없으면 403). items가 빌 때까지
   page 증가 → 전체 글 목록.
2. **본문**: `https://m.blog.naver.com/{blogId}/{logNo}` — 서버렌더 HTML의 `se-main-container`
   div에 SmartEditor 본문이 통째로 있음. 이미지도 여기서(pstatic.net 도메인).
3. RSS(`rss.blog.naver.com/{blogId}.xml`, 리다이렉트 따라갈 것)는 최근 글 폴백.

전 과정이 `scripts/fetch_naver_blog.py`로 자동화되어 있다:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_naver_blog.py \
  --blog-id {blogId} --outdir .scrape-out/{slug} --max-posts 200
```

**두 가지 블로그를 구분하라:**
- **조직 공식 블로그** (own-site/Place의 링크에서 blogId 발견) — 그 조직 자신의 콘텐츠.
  전문(full text)+이미지 수집, `posts` 컬렉션에 저장. 이미지는 썸네일 후보 자격 있음.
- **제3자 후기 블로그** (블로그 검색 결과) — 남의 저작물. **사실만 추출**(시술명·가격 언급·
  평가 요지)해 해당 컬렉션에 provenance와 함께 병합. 전문 저장·이미지 재사용 금지.

## ⭐ 왜 플랫폼이 가격의 유일한 공개 소스인가 (병원 필독)

**한국 병원 홈페이지에는 시술 가격이 거의 없다.** 의료광고 규제로 자사 사이트는
비급여수가표(제증명 수수료 정도)만 싣고 시술 가격은 뺀다(실측: 한 의원 홈페이지 가격
0건, 제증명 33,000원만). **진행 중인 이벤트가와 시술 가격은 시술 플랫폼에만 공개된다.**
따라서 병원 스크래핑에서 이 플랫폼들은 "보충용"이 아니라 **가격·이벤트의 1차 소스**다.
홈페이지만 긁고 끝내면 커머스(product) 데이터가 통째로 비어 버린다.

다만 **어느 플랫폼을 어떻게 확보하느냐는 아래 robots 판정이 정한다** — 여신티켓은 직접
수집, 강남언니는 소유자 경로. 둘 다 막히면 커머스는 비는 게 정상이고, 그건 `gap`으로
정직하게 남긴다.

## 플랫폼 접근 정책 — robots.txt가 경로를 결정한다 (2026-08-25 실측)

**렌더링 능력과 수집 허가는 별개다.** Claude Browser는 두 사이트를 모두 정상 렌더한다
(헤드리스가 받던 403·빈 셸이 아니다). 그러나 **긁어도 되는지는 robots.txt가 정한다.**
도메인마다 `{origin}/robots.txt`를 먼저 읽고 그 판정을 digest의 `robots` 필드에 남겨라.

### ⚠️ 먼저: 어느 User-agent 그룹이 우리에게 적용되는가

**RFC 9309 — 이름이 명시된 그룹이 `*`보다 우선하고, 명시 그룹은 `*`의 Disallow를 상속하지
않는다.** 그래서 `User-agent: *`만 보고 판단하면 정반대 결론이 나온다(실측으로 한 번 틀렸다).

우리를 가리키는 이름은 **`Claude-User`**(사용자 요청으로 동작하는 에이전트 = Claude Browser)
와 `Claude-SearchBot`이다. **`ClaudeBot`은 학습용 크롤러라 우리가 아니다.** robots에
`Claude-User` 그룹이 있으면 **그 그룹만** 적용된다. 확인 순서:

1. `Claude-User` 그룹이 있는가 → 있으면 그 그룹의 Allow/Disallow가 전부다. 끝.
2. 없으면 → `*` 그룹이 적용된다.
3. `ClaudeBot`만 차단돼 있고 `Claude-User`가 허용이면 → **수집 가능**. 둘은 다른 에이전트다.

| 플랫폼 | 우리에게 적용되는 그룹 | 판정 |
|---|---|---|
| **여신티켓** yeoshin.co.kr | `ClaudeBot` 명시 그룹 존재(`Allow: /`, `Crawl-delay: 1`), `*`도 `Allow: /` + `Crawl-delay: 5` | ✅ **수집.** 보수적으로 5초 간격. 차단: `/cart` `/myPage` `/payment` `/api` `/admin` `/_next/data` `/callback` `/auth` |
| **강남언니** gangnamunni.com | **`Claude-User`: `Allow: /`** (차단: `/static/` `/reviews` `/community`) | ✅ **수집.** 단 **후기·커뮤니티는 진입 금지** — 이벤트·가격은 `/hospitals/{id}`로 허용 |
| **바비톡** babitalk.com | `*`: `Allow: /` (차단: `/elb-status` `/sentry-example-page` `/login` `/mypage`) | ✅ **수집.** `babitalk.kr`은 미해석 — `.com`이 정본 |

> ℹ️ 강남언니 robots 주석의 *"AI training crawlers (GPTBot, ClaudeBot, CCBot…) are
> intentionally not listed"*는 **학습 크롤러**를 겨냥한 문장이고, 바로 위에 `Claude-User`·
> `Claude-SearchBot`·`ChatGPT-User`·`OAI-SearchBot`을 개별 허용해 두었다. 헤더의
> `Content-Signal: search=yes, ai-input=yes, ai-train=no`도 같은 취지 — **AI 입력은 허용,
> 학습은 금지**. 즉 이 스킬의 수집은 허용 범위이고, 수집물을 모델 학습에 쓰는 것은 금지다.

**바뀌지 않는 것:** 허용된 그룹이 없어 `Disallow: /`가 적용되면 그때는 진짜로 수집하지
않는다. User-Agent 위장·주소 변경·인터스티셜 해제로 우회하는 것은 이 스킬과 `org-evidence`
계약의 범위 밖이고 스킬 내부에서 해제할 수 없다. 그 경우의 정답은 우회가 아니라 **소유자**다.

### 수집이 허용된 플랫폼에서의 진행 순서

1. **Claude Browser로 열고 `get_page_text` 1회** — 대부분 이 한 번에 시술명·정가·할인율·
   이벤트가·평점이 텍스트로 나온다(실측). 비면 3초 대기 후 재독, 그다음 스크롤.
2. **검색은 사이트 내 검색창으로**, URL 추측 금지. 이벤트 목록이 무한스크롤이면
   `dynamic-capture.md`대로 끝까지 로드.
3. **페이지가 쓰는 내부 JSON API를 직접 호출하지 말 것.** UI가 URL로 안 몰리면 그건
   `gap`이지 내부 엔드포인트를 부를 근거가 아니다.
4. **미국 리전 검색엔진 표본은 순위·존재 증거로만**, 국내 노출 주장 금지.

### 소유자 연결 경로 (막힌 플랫폼의 정답)

세미나 참석 원장님은 **자기 병원의 owner**라 자기 데이터에 접근할 권리가 있다:

- 플랫폼 **파트너센터/병원 관리자 페이지**(이미 로그인된 본인 Chrome) — `aside`로 구동하거나
  원장님이 직접 내보내기
- 진행 중 이벤트 목록의 CSV·스크린샷을 `.scrape-out/{slug}/owner/`에 투입
- 원장님이 현재 이벤트가를 구두로 확인

`source: "owner-provided"` + 날짜로 기록한다. **owner-provided 가격은 모든 스크랩 소스보다
우선한다** — 자기 가격의 권위자는 원장님이고, 플랫폼 리스팅은 낡았을 수 있다. 반대로
경쟁사 가격에는 소유자 경로가 없으므로, 막힌 플랫폼은 그대로 `gap`으로 남긴다.

## 강남언니 (hospital) — ✅ 수집 가능(후기·커뮤니티 제외), 이벤트가 1순위

`Claude-User` 그룹이 `Allow: /`라 **Claude Browser로 수집한다.** 단 robots가 막은
**`/reviews`·`/community`·`/static/`은 진입 금지** — 후기 본문과 커뮤니티 글은 수집 대상이
아니고, 필요하면 리뷰 **수·평점 같은 집계 지표만** 병원 상세에서 읽는다.

**진입 경로(실측):**
- 병원 상세는 `/hospitals/{id}`, 디렉터리는 `/hospitals`(전체 1,615건, 무한스크롤 + 지역 필터).
- ⚠️ **데스크톱 웹 검색은 URL로 구동되지 않는다.** `/search?keyword=<병원명>`은 200을 주고
  `__NEXT_DATA__.query.keyword`에 값도 담기지만 렌더는 `''에 대한 검색결과`이고 검색 요청
  자체가 발생하지 않는다. 오버레이 검색창도 Enter로 제출되지 않는다.
- 따라서 **`/hospitals` 디렉터리를 지역 필터로 좁혀 상호를 찾는 경로**를 쓴다. 내부 JSON
  API(`/api/solar/...`) 직접 호출은 금지.

추출 목표:

- **이벤트별로**: 시술명, **이벤트가(할인가)**, **정가(원가)**, 할인율, 옵션/용량(예:
  "리쥬란 2cc"), 기간, 조건(첫방문/제휴 등). events + offerings.commerce 양쪽을 채운다.
- 시술 목록·의사 프로필·리뷰 수·평점도 함께.
- 이벤트가는 `promotions`(kind/benefit_type/value/기간/target), 원가는
  `offerings.commerce{price, sale_price, status}`로 매핑.
- **이미지는 데이터 추출용으로만 — 썸네일 재사용 금지(저작권).**
- 상호를 디렉터리에서 못 찾으면 `available-but-empty`(미입점), 접근이 막히면 `access-failed`.

## 여신티켓 (hospital) — ✅ 수집 가능, 이벤트/패키지 딜

yeoshin.co.kr — robots가 `Allow: /`에 `Crawl-delay: 5`이므로 **Claude Browser로 수집한다.**
`/cart` `/myPage` `/payment` `/api` `/admin` `/_next/data` `/callback` `/auth`는 진입 금지,
요청 간 5초를 지킨다.

**JS 앱**이라 초기 로드는 인기검색어·프로모션 배너만 뜬다(실측). 검색창에 상호를 입력하고
결과가 렌더될 때까지 대기한 뒤 병원 상세로 진입해 이벤트·패키지 딜을 읽는다. 앱 우선
사이트이므로 `resize_window {preset:"mobile"}`로 모바일 뷰포트에서 더 잘 열린다.
추출 목표: 시술명·이벤트가·정가·옵션·기간. 패키지(묶음 딜)는 구성 시술과 총가를 함께
기록. events + offerings.commerce 보강.

## 바비톡 (hospital) — 가격 교차검증

babitalk.kr — 후기·가격 비교. 같은 시술의 이벤트가를 강남언니/여신티켓과 **교차검증**해
플랫폼 간 가격 차이를 conflict가 아니라 "플랫폼별 이벤트가"로 병기. cases(review) 지표와
가격 샘플 보강.

## 로톡 (law)

lawtalk.co.kr — **사이트 내 검색창으로** 변호사명/법인명 검색 (URL 추측 금지:
`/directory?keyword=`는 404). 검색결과 카드는 텍스트로 읽히지만, **변호사 상세
프로필은 커스텀 엘리먼트 onclick JS 내비게이션이라** ref 클릭이 헤드리스에서
실패한다(실측) — `find text "<변호사명>" click` 시도 후 안 되면, 카드 수준 정보만
확보하고 상세는 미확보로 기록. 변호사 프로필(경력·출신·수임료 공개 시), 의뢰인 후기,
분야별 활동. people·cases 보충. 프로필 사진은 재사용 금지.

## Google (모든 업종)

`google.com/search?q={상호}+시술|변호사|세무사` — 공식 사이트 확인, 영문 정보,
Google Maps(시간/리뷰). law/tax는 뉴스 검색 결과도 press 후보로.

---

## Research priority (충돌 해소의 근거)

| 사실 | 신뢰 순위 |
|---|---|
| 명칭·설명 | own-site > 그 외 (own-site 명칭이 canonical, 나머지는 aliases) |
| 가격 (hospital) | **owner-provided > 강남언니 > 여신티켓 > own-site > 바비톡** |
| 영업시간·주소·전화 | Naver Place > own-site |
| 인물 경력 | own-site > 로톡/강남언니 |
| 언론보도 | 매체 원문 링크 > 자체 사이트 보도 모음 |

## Cross-referencing tips

- 같은 시술이 플랫폼마다 다른 이름(보톡스/보툴리눔 톡신) — own-site 이름으로 통일, 나머지는 aliases
- 여러 플랫폼에 반복 등장 = 그 조직의 주력 → raw.json에 빈도 기록(entity-setup의 상단 배치 근거)
- 카테고리 구조도 플랫폼마다 다름 — own-site의 네비 구조를 기본 골격으로

## 운영 규약 (모든 에이전트 공통)

- **Claude Browser가 기본 렌더러.** WebFetch/WebSearch 금지 (JS 렌더 불가로 데이터가 깨짐)
- **에이전트당 탭 1개**: `tabs_create {foreground:false}` → 모든 호출에 `tabId` 전달 →
  종료 전 `tabs_close`. `preview_start`는 메인 스레드만, `tabs_select`는 호출 금지
- 폴백 순서: aside(소유자 로그인 세션이 필요할 때) → agent-browser(헤드리스).
  agent-browser 사용 시 세션당 `--session <이름> --profile /tmp/ab-<이름>` 격리 필수
- `pkill chrome` · `close --all` 금지 (preflight에서 메인 스레드만)
- **도메인마다 robots.txt 먼저 확인**하고 판정을 digest `robots` 필드에 기록
- 실패 시: 자기 탭/세션 close → 1회 재시도 → 그래도 실패면 부분 결과 + 에러 보고 (최대 2회)
- 요청 간 예의: `Crawl-delay` 준수(없으면 짧은 대기), 한 사이트 50페이지 상한
