# Industry profiles — what to collect, per business type

The output contract's collection keys are fixed (`offerings / people / cases / press /
events / faqs`); each industry maps its own vocabulary onto them. `tax` inherits `law`
and swaps the offerings vocabulary.

## Auto-detection (when the user doesn't specify `industry`)

Check, in order — first hit wins:

1. **Org name / title tag keywords**
   - `의원 | 피부과 | 성형외과 | 치과 | 한의원 | 클리닉 | 병원` → `hospital`
   - `법무법인 | 변호사 | 로펌 | law firm` → `law`
   - `세무법인 | 세무사 | 회계법인 | 회계사` → `tax`
2. **Homepage nav vocabulary** — `시술|진료과목` → hospital · `업무분야|승소사례` → law ·
   `기장|세무조사|절세` → tax
3. Still ambiguous → ask the user. Never guess silently; record the decision in `report.md`.

## Profile gate — read the scope profile in `SKILL.md` first

The checklist below is the **`launch`** roster. In **`seminar`** the following are
`skipped-by-profile`, not gaps: 블로그 **본문**(제목·날짜는 수집), Phase 2 이미지 다운로드·비전
판독, 채널 상세 지표, cases·press, 그리고 **가격 1차 소스가 아닌 보조 플랫폼**. 자사 시술 상세는
주력 10~15개로 제한한다(`platforms.md`의 카탈로그 우선 규칙).

⚠️ **이미지 스킵은 조건부다.** 카탈로그에 텍스트 가격이 없으면 가격이 이미지에 구워진 사이트이므로
`seminar`에서도 비전 판독은 **필수**다. 스킵 전에 텍스트 가격 존재를 반드시 확인하라.

## ⭐ Forced collection checklist (S1 — discretion removed)

v1 skipped the Naver blog at an agent's discretion and the build went ahead blind. Now:
**every source below ends in exactly ONE of two states — `collected`, or a written `gap`
entry (source, what's missing, why, retryable?) in the collector's digest. Silently
skipping a listed source is a defect.**

| source | 병원 | 법무 | 세무 | non-negotiable notes |
|---|---|---|---|---|
| own-site **full nav walk** | ✅ | ✅ | ✅ | EVERY menu leaf (not top pages); + `extract_images.js` per page |
| Naver Place | ✅ | ✅ | ✅ | 주소·전화·시간·리뷰 수·공식블로그 링크 |
| **Naver 공식 블로그 전문** | ✅ | ✅ | ✅ | 블로그가 존재하면 `fetch_naver_blog.py`로 **전 글** — 재량 스킵 금지 |
| **강남언니 + 여신티켓 (+ 바비톡)** | ✅ | — | — | ⭐ **가격·이벤트의 1차 소스** — 홈페이지엔 가격이 없다(의료광고 규제). **진행 중 이벤트가·정가·옵션·기간** 수집. robots는 `*`가 아니라 **`Claude-User` 그룹**으로 판정할 것 — 셋 다 현재 허용(강남언니는 `/reviews`·`/community` 제외, 여신티켓은 `Crawl-delay: 5`). 강남언니 진입은 `/hospitals` 디렉터리→`/hospitals/{id}` (검색은 URL로 구동 안 됨) |
| 로톡 | — | ✅ | — | 프로필·사례·후기 |
| Naver/Google **뉴스** | 선택 | ✅ | ✅ | law/tax: `"{상호}" 변호사/세무사` 뉴스탭 |
| Google Maps | ✅ | ✅ | ✅ | 평점·영문명·채널 |

**Digest format (what each collector RETURNS — 1–2k tokens; raw goes to `raw/`):**
```jsonc
{ "source": "own-site", "status": "collected",
  "counts": { "pages": 41, "offerings": 34, "people": 6, "images": 480, "posts": 0 },
  "notable": ["가격표는 /noinsuPrice 이미지에만 존재", "전후 전용 페이지 /bna 있음"],
  "refs": ["raw/home.txt", "raw/cat-*.txt", "…"],        // corpus refs, not content
  "gaps": [ { "what": "후기 본문", "why": "로그인벽", "retryable": false } ] }
```
No prose dumps, no raw HTML in the return — the digest is what the librarian and the
Architect read. High-value finds (price table, before-after set, blog corpus) MUST appear
in `notable` so the plan can't miss them.

## hospital

| collection | 무엇 | 필수 필드 | 비고 |
|---|---|---|---|
| offerings | 시술/진료 | name, category, description, duration + **commerce{price,sale_price,status}** | 콘텐츠(entity)+커머스(product) 둘 다. **홈페이지엔 가격이 거의 없으니 commerce는 강남언니·여신티켓 이벤트가로 채운다** — 그래도 없으면 commerce=null(정상) |
| people | 의료진 | name, title(원장 등), roles(담당시술), career | 사진 매칭 중요 |
| cases | 전후사진·후기 | kind=before-after/review, related_offering | 민감 진료과는 스킵 |
| press | (드묾) | — | 있으면 수집, 없어도 미해결 아님 |
| promotions | 이벤트/할인/쿠폰/혜택 | kind, benefit_type, value, starts_at, ends_at, target | product 아님(정가는 offering.commerce). ⭐ **진행 중 이벤트가는 여신티켓(수집 가능)과 소유자 제공 자료가 1차 소스**, 홈페이지 이미지 배너는 Claude 비전 판독으로 보강 |
| faqs | 자주 묻는 질문 | q, a | |

**병렬 에이전트 배정 (4) — 한 메시지로 동시 spawn, 각자 자기 탭:**
① own-site(전체 크롤+이미지) ② Naver(검색→Place→블로그) ③ **가격·이벤트 전담 —
강남언니+여신티켓(+바비톡)**: Claude Browser 모바일 뷰포트로 병원 상세→이벤트/패키지 딜에서
시술명·이벤트가·정가·옵션·기간 전량 수집. 강남언니는 `/hospitals` 디렉터리로 진입하고
`/reviews`·`/community`는 건드리지 않는다, 여신티켓은 `Crawl-delay: 5` 준수
④ Google Maps(평점·영문명·채널)

각 에이전트는 `tabs_create {foreground:false}`로 자기 탭을 열고 **모든 브라우저 호출에
그 `tabId`를 넘긴 뒤** 종료 전 `tabs_close`한다. 탭을 안 나누면 서로의 페이지를 읽는다 —
`references/claude-browser.md` 참조.

## law

| collection | 무엇 | 필수 필드 | 비고 |
|---|---|---|---|
| offerings | **업무분야** (형사/이혼/기업자문…) | name, category(민사/형사/가사…), description | 가격 비공개가 정상 → commerce=null. 상담료 공개 시만 commerce |
| people | **변호사** | name, title(대표/파트너/소속), roles(담당분야), career(출신·경력), credentials(자격·학력) | 프로필 사진 매칭 중요 |
| cases | **성공사례** | kind=success-case, title, summary(사건 개요), result(무죄/승소/감형 등), related_offering | 개인정보 익명화된 원문 그대로 |
| press | **언론보도** | title, outlet(매체), date, url | 네이버 뉴스 검색 병행 |
| promotions | (드묾 — 무료상담 이벤트 정도) | kind=benefit, condition | 있으면 수집 |
| faqs | 상담 FAQ | | |

**병렬 에이전트 배정 (3):** ① own-site ② Naver(검색+**뉴스 탭**: `"{상호}" 변호사`)+로톡
③ Google(+구글 뉴스)

## tax — law 상속

law 프로파일과 동일 구조. 차이만:

- offerings 어휘: 기장대리 / 세무신고 / 절세 컨설팅 / 세무조사 대응 / 조세불복 / 상속·증여
- people: 세무사·회계사 (자격 표기: 세무사 제N회 등)
- cases: 절세 성과·불복 인용 사례 (금액이 있으면 result에)
- press: 보도 + **칼럼 기고** (전문지 기고가 흔함 — outlet에 매체명)
- 소스: 로톡 대신 없음 — ① own-site ② Naver(검색+뉴스) ③ Google

## 공통: posts 컬렉션 (조직 공식 네이버 블로그)

모든 업종에서, own-site나 Naver Place에 공식 블로그 링크가 있으면 `fetch_naver_blog.py`로
**전체 글**을 수집해 `posts` 컬렉션에 담는다 (병원: 시술 후기·안내글 / 법무·세무: 칼럼·
사례 해설 — cases·press의 원천이 되기도 함). 컴파일 단계에서 각 글을 관련 offering에
`topics`로 매칭한다. 제3자 블로그는 posts에 넣지 않는다 (platforms.md 참고).

## 공통 필수 (업종 무관)

- **legal**: 대표자·사업자등록번호·전화 — 푸터에서. 없으면 null + report 미해결 등재
- **brand**: 로고 후보(이미지+파비콘)·브랜드 컬러 — own-site 에이전트가 extract_images.js로
- 가짜 데이터 생성 절대 금지 — 못 찾으면 null/빈 배열 + sources 없음이 정답
