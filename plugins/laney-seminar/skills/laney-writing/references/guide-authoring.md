# Laney 가이드 작성 규칙

조직 관리자가 읽는 공개 제품 가이드에 적용합니다. 먼저
[`writing-principles.md`](writing-principles.md)를 읽습니다.

## 독자와 필요부터 정하기

주 독자는 Laney를 설정하고 운영하는 조직 관리자입니다. 한 문서는 관리자가 기능을 배우거나,
한 작업을 끝내거나, 정확한 사실을 찾거나, 개념 사이의 관계를 이해하도록 도와야 합니다.
초안을 쓰기 전에 한 가지 필요를 고릅니다.

| 유형 | 독자의 필요 | 문서 구조 |
|---|---|---|
| `tutorial` | 안전한 결과를 만들면서 처음 배우기 | 결과, 사전 조건, 단계, 결과 확인, 다음 단계 |
| `how-to` | 이미 아는 한 작업을 끝내기 | 목표, 조건, 단계, 결과 확인, 문제 해결 link |
| `reference` | 정확한 사실 찾기 | 중립 설명, field·option, 제약, 관련 page |
| `explanation` | 개념의 이유와 관계 이해하기 | 맥락, model, 결과, 관련 작업 |

네 유형을 한 긴 page에 섞지 않습니다. navigation은 제품과 업무를 기준으로 구성하고,
frontmatter의 `type`으로 Diátaxis 유형을 기록합니다.

## 기능과 업무 가치를 연결하기

공개 가이드는 기능이 운영상 필요한 이유를 설명해야 합니다. 검증하지 않은 성과를 약속하지
않으면서 다음 가치 흐름을 보여 줍니다.

1. 고객 또는 운영 문제를 밝힙니다.
2. Laney가 업무를 어떻게 바꾸는지 설명합니다.
3. 조직이 추구할 수 있는 업무 결과를 적습니다.
4. 결과를 확인할 지표를 적습니다.

설정이나 참여자가 여러 가지라면 합성 예시임을 분명히 밝히고 설명합니다. 병원, 학원, 소매점,
전문 서비스, 여러 지점이 있는 조직을 예시로 사용할 수 있습니다. 가상의 회사, 금액, 전환율,
성과 개선을 실제 고객 결과처럼 쓰지 않습니다.

선택한 문서 유형을 바꾸지 않는 범위에서 다음 내용을 더합니다.

| 유형 | 추가할 업무 맥락 |
|---|---|
| `tutorial` | 현실적인 시작 상황 하나와 학습 결과를 확인할 지표 |
| `how-to` | 운영 가치, 대표 상황 하나, 결과 지표 |
| `reference` | 이 자료가 돕는 판단과 설정 예시 하나 |
| `explanation` | 문제, 가치, 결과, 측정 방법, 서로 대비되는 예시 두 개 |

## 필수 frontmatter

locale별 MDX page에는 다음 field를 둡니다.

```yaml
title: 폼 만들고 게시하기
description: 폼을 만들고 응답 대상을 정한 뒤 안전하게 게시합니다.
type: how-to
audience: org-admin
area: forms
status: published
owner: product-operations
lastVerified: 2026-08-04
outcome: 의도한 접근 link에서 test를 마친 폼을 사용할 수 있습니다.
```

`tutorial`과 `how-to`에는 `outcome`이 필요합니다. `reference`와 `explanation`에는 넣지
않습니다. 현재 제품, code, 자동 test로 내용을 확인한 뒤에만 `lastVerified`를 갱신합니다.

## 한국어 문서

- 존댓말을 사용하고 관리자에게 직접 안내합니다.
- 행동보다 조건을 먼저 씁니다.
- 번호가 있는 한 단계에는 한 행동만 둡니다.
- 화면에 보이는 control은 제품의 정확한 한국어 label을 사용합니다.
- code, field key, enum value, error message는 바꾸지 않습니다.
- label 뒤에 토막 문장을 붙이기보다 완결된 문장을 씁니다.
- 한국어에 영어 단어 수 제한을 적용하지 않습니다.
- AI 문체와 번역투를 검토할 때에는 [`korean-naturalness.md`](korean-naturalness.md)를
  적용합니다.

## 영어 문서

[SimpleEnglish](https://github.com/AminBlg/SimpleEnglish)의 실용적인 규칙을 적용합니다.
이 자료는 ASD-STE100 원칙을 참고하지만 공식 compliance 도구는 아닙니다.

- 절차는 명령형으로 씁니다.
- 한 문장에 한 지시만 둡니다.
- 의미가 유지된다면 절차 문장은 20단어 이하, 설명 문장은 25단어 이하로 씁니다.
- 사실은 단순 현재형으로 씁니다.
- modal이 필요하면 `can`, `will`, `must`를 우선합니다.
- `should`, `would`, `may`, `might`, `could`가 모호하지 않은지 확인합니다.
- 한 문단에는 한 주제만 둡니다.
- code, UI label, identifier, command, 인용한 error를 바꾸지 않습니다.

영어 page는 한국어를 직역한 문장이 아니라 localization입니다. 한국어 page의 사실, 결과,
경고, link는 그대로 보존해야 합니다.

## media

video는 관리자가 한 작업을 끝내는 과정을 보여 줍니다. video만으로 업무를 배워야 하게 만들지
않습니다.

- 합성 data를 사용합니다.
- 시작 상태와 저장한 결과를 보여 줍니다.
- page 언어로 caption을 제공합니다.
- video 옆에 text 요약과 결과 확인 방법을 둡니다.
- 관리자가 실제 고객 제출 동작을 확인해야 할 때에만 고객 제출 화면을 포함합니다.

## link와 reference data

locale-relative link를 사용합니다. MDX link에 `/ko` 또는 `/en`을 hardcode하지 않습니다.
이미 구현 registry가 정본이라면 reference content를 code에서 생성합니다.

내부 제안, database path, issue ID, 구현 메모는 공개 가이드에 넣지 않습니다.
`skills/laney-repo/references/engineering`으로 옮기고 내부 문서에서만 연결합니다.

## 검토 순서

1. 독자와 Diátaxis 유형을 확인합니다.
2. 현재 UI, code, test로 제품 사실을 확인합니다.
3. `terminology.yml`에서 용어를 확인합니다.
4. 한국어 page를 작성하고 업무를 실제로 검증합니다.
5. 영어 규칙에 따라 영어 page를 localization합니다.
6. `pnpm docs:lint`, type check, docs build를 실행합니다.
7. browser에서 navigation, 검색, 언어 전환, mobile layout, media를 확인합니다.
