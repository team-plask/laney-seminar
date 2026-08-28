# 레이니 플랫폼 모델 — 상세 레퍼런스

개념 지도(SKILL.md)의 상세판. 레포 코드·마이그레이션에서 추출한 사실만 담는다.
스키마 정본은 `supabase/migrations/`, 의미론 정본은 `packages/framework/src/impl/*.ts`.

## 1. 데이터 모델

### organizations — 병원의 공간
`slug`(서브도메인이 됨), `name`, `logo`, `theme`, `default_locale`(en|ko|ja|zh),
`business`(통신판매 사업자 고지), **`assistant_intro`(챗 첫인사 + 추천 칩 jsonb)**,
`parent_id`(본점-지점 계층). 모든 테넌트 테이블이 `organization_id`로 격리된다.

### entities + entity_edges — 유일한 콘텐츠 원시형
- 노드: `name`(내부 라벨·검색키) + 로컬라이즈 `label`/`slogan`/`description`
  (jsonb `{en,ko,ja,zh}`) + `image`(URL)/`icon`/`slug`/`position`.
- **`slug`가 있으면 그 노드가 `/slug` 페이지가 되고** 카드가 자동 링크된다.
- 부모-자식은 트리가 아니라 **그래프**(`entity_edges(parent_id, child_id, position)`)
  — 한 노드를 여러 부모 아래 재사용할 수 있다.
- 검색은 label/slogan/description 전 로케일을 본다 (중·일 검색어도 매칭).

### products + product_edges — 가격이 붙는 판매 단위
- `kind`: one_time | recurring | usage | bundle. `cycle`(구독 주기), `price`,
  `status`(active|draft|archived), `entity_id`(연결 콘텐츠).
- **번들 가격은 항상 자식 합으로 파생** — 번들 할인은 프로모션으로만 표현한다.
- 고객·랜딩 액터는 `status=active`만 본다. draft는 존재하지 않는 것과 같다.

### promotions — 카탈로그와 분리된 날짜 규칙
- `kind`: event(기간 내 자동 적용) | coupon(`code` 필요) | benefit(산문 조건).
- `benefit_type`: price(고정 이벤트가) | percent | amount_off | gift. `value`,
  `applies_to`(all|one_time|recurring), `months`(첫 N주기 — "첫 달 무료" =
  percent 100 × recurring × 1), `stackable`, `starts_at/ends_at`, `status`.
- **부착 3축뿐**: `product_id` 명시 → 같은 `entity_id` 공유 → 타깃 없음(조직 전체).
  이름 문자열 매칭은 절대 없다.

### templates — `${…}` 자리표시자 텍스트
`kind`: **prompt**(챗봇 시스템 프롬프트), dashboard(관리자 어시스턴트),
message(정형 답변), 알림톡 등 발송류. `account_id`가 있으면 그 채널의 오버레이.

### sections — 화면 조립 (자체 콘텐츠 없음)
`type` + `entity_id` + `path`(""=홈) + `position` + `cta` + `options`.
참조한 엔티티의 **서브트리를 걸어서** 렌더한다:

| type | 렌더 | 자식 필요? |
|---|---|---|
| header / footer | 크롬 (자식=메뉴/컬럼, 손자=드롭다운/링크) | 필요 |
| content | 범용 프레임: 제목군+이미지+CTA (구 hero/cta 흡수) | 불필요 |
| features | 자식들을 카드·아코디언·갤러리 그리드로 | 필요 |
| faqs | 자식=Q&A (자식이 손자를 가지면 카테고리 그룹) | 필요 |
| steps / stats | 자식을 번호 단계 / 카운트업 수치로 | 필요 |
| logos / marquee | 자식 image를 로고 열 / 무한 슬라이드로 | 필요 |
| testimonials | 자식을 후기 카드로 | 필요 |
| markdown | 긴 글 | 불필요 |

`fields` 옵션으로 엔티티 필드→역할 매핑(기본 tag=name, heading=slogan,
description=description). `tone`(background/muted/primary/secondary/foreground).

### accounts — 채널 (16종 플랫폼)
dashboard, landing, kakaoOauth, kakaoCallback, lineOauth, metaOauth, lineChannel,
whatsapp, messenger, instagram, kakaoChannel, kakaoBiz(발송 전용), wechat,
googleCalendar(아웃바운드), phone(실시간 음성), vegas·hairzzang(CRM 싱크).
조직당 `landing` 계정 하나가 웹사이트 채팅·폼의 액터다.

### customers / conversations / reservations
- customers `status`: lead → qualified → active → churned/lost.
  **랜딩 채팅 리드와 폼 리드는 같은 landing 계정을 달고 생성돼 한 고객으로 통합.**
- conversations `status`: open|pending|snoozed|closed + **`ai_paused`**:
  멤버가 직접 답장하면 자동 true(인수인계), 재개는 대시보드 토글.
- reservations `status`: pending|confirmed|completed|cancelled|no_show.
  **availability_rules**(hours|block|capacity|gap)가 예약 삽입과 미리보기를
  같은 함수로 판정 — 영업시간·휴무·정원·간격을 조직이 규칙으로 정의.

### members / roles — RBAC
`roles.permissions`는 `<impl>.<method>` 문자열 배열, `'*'`는 전량 통과.
가입 시드 4종: owner=`['*']`, admin(콘텐츠·운영 관리), member(조회 위주),
**customer(웹 방문자에게 부여되는 상한: products.list/all, reservations.
insert/list/update/cancel/availability, customers.profile)** — 이것이 곧
상담봇이 고객 대신 할 수 있는 일의 전부다.

## 2. 챗봇 런타임

- **프롬프트 병합**: 조직 base prompt(account 없는 kind=prompt 템플릿) +
  채널 오버레이(계정 템플릿 → 없으면 플랫폼 기본). 대시보드 어시스턴트는
  kind=dashboard 템플릿.
- **도구**: 액터 권한으로 필터된 impl 메서드가 그대로 도구가 된다. 고객 채널은
  public 표면으로 축소 — customer 역할 권한이 상담봇의 능력 상한.
- **products__quote — 유일한 가격 도구**: 부분 문자열을 전 로케일 이름에 매칭
  (최대 40건) → 프로모션 3축 부착 판정(날짜 유효성 포함) → 번들은 자식 합산 →
  `regular_price/sale_price/final_price` 또는 구독·복합은 `pricing[]`.
  희망 방문일(`date`)을 받아 그 날짜 기준으로 이벤트를 판정한다.
- **첫인사**: `organizations.assistant_intro` → `{greeting, suggestions[]}`.
  미설정 시 로케일 기본값("안녕하세요! 무엇을 도와드릴까요?" + 칩 2개).
  **말투 조정 시 첫인사·추천칩은 organizations__update, 말투 규칙은 프롬프트 템플릿.**

## 3. 랜딩 렌더링

- 호스트 해석: `{slug}.{루트도메인}` → 슬러그 직해석 (도메인 행 불필요),
  커스텀 도메인은 `domains`에서 **verified 행만**. 루트 도메인: preview.laney.app.
- 로케일: 기본 로케일 + **엔티티에 실제 번역이 있는 로케일만** 노출
  (빈 번역 페이지 방지). 기본 로케일은 URL 접두사 없음.
- 캐시: 섹션·엔티티는 태그 캐시 — 대시보드 저장이 즉시 재검증.

## 4. 자동 프로비저닝 (가입 시)

`workspace_signup` 트리거: 조직 생성(가입 폼의 병원 이름) + 가입자를 owner로.
`organizations_seed_defaults` 트리거: 역할 4종 + landing 계정('Website') 생성.
→ **가입 직후 상태 = 빈 카탈로그 + 뜨는 채팅 + owner 권한.** 여기서부터가 우리 일.

## 5. MCP 경계 제약 (LNY-1527)

insert/update 스키마에서 참조 필드가 벗겨진다: sections.entity_id,
entity_edges.parent_id/child_id, products.entity_id, reservations.customer_id,
conversations.account_id/customer_id, messages.conversation_id.
계획에는 "1회 시도 → 실패 시 안내 후 진행"으로 넣는다.

## 6. 정본 문서

사용자 문서 정본: `skills/laney-product/references/guide/` (MDX, ko/en) —
start(런치 체크리스트)·commerce(상품→견적)·website(발행)·availability(영업시간
규칙)·channels 등 영역별. 에이전트 호출 정책은 `references/runtime.md`.
이 레퍼런스와 충돌하면 정본이 이긴다.
