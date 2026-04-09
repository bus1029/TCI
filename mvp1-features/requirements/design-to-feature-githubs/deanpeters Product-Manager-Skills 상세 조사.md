# deanpeters/Product-Manager-Skills 상세 조사

- 조사 대상: `deanpeters/Product-Manager-Skills`
- 조사 목적: TCI의 기능 기획을 문제 정의, PRD, 스토리, 로드맵 수준의 설계 입력 전 단계 문서로 구조화할 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 저장소, 공식 README, 공식 command/skill 문서, 공식 releases 페이지, 최신 커밋 메타데이터 중심

## 1. 한줄 결론

`deanpeters/Product-Manager-Skills`는 TCI가 가진 기능 아이디어를 `문제 정의 → discovery → PRD → epic/story → roadmap` 흐름으로 정제하는 데 강한 PM 스킬 프레임워크다. 특히 각 스킬이 교육적 설명과 안티패턴까지 포함해 팀의 사고 기준을 맞추는 데 유리하다. 다만 `tech spec`, `architecture`, `contracts` 같은 기술 설계 산출물은 중심이 아니므로, 기술 설계 프레임워크의 대체재보다는 PM 정제와 팀 표준화 레이어로 보는 편이 맞다

출처: [README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md), [discover command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/discover.md), [write-prd command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/write-prd.md), [plan-roadmap command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/plan-roadmap.md), [prd-development skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md)

참고: 아래 문서의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 discovery에서 PRD와 roadmap까지 이어지는 기본선이 있다

공식 README는 이 저장소를 `47 ready-to-use PM skills + reusable command workflows`로 설명하고, command 계층으로 아래 6개 흐름을 제공한다

- `discover`
- `strategy`
- `write-prd`
- `plan-roadmap`
- `prioritize`
- `leadership-transition`

TCI 관점에서 중요한 점은 `discover → write-prd → plan-roadmap` 흐름이 이미 명시돼 있다는 점이다. 즉, 기능 아이디어를 곧바로 구현으로 넘기지 않고, 문제 정의와 문서화, 우선순위화, 로드맵화 단계를 사이에 둔다

출처: [README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md), [commands README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/README.md), [discover command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/discover.md), [write-prd command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/write-prd.md), [plan-roadmap command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/plan-roadmap.md)

### 2.2 `prd-development`가 PM 문서화를 꽤 깊게 다룬다

핵심 workflow skill인 `prd-development`는 단순 PRD 템플릿이 아니라 8개 단계, 2-4일 분량의 작성 흐름을 정의한다. 내부적으로 아래 항목을 묶는다

- executive summary
- problem statement
- target users and personas
- strategic context
- solution overview
- success metrics
- epic hypothesis
- user stories and requirements
- out of scope
- dependencies and risks
- open questions

TCI에 필요한 것은 "기능 요약"이 아니라 "개발 전에 읽을 수 있는 요구사항 문서"다. 이 스킬은 문제 정의에서 스토리까지 이어지므로, 현재 기능 카탈로그를 실질적인 handoff 문서로 바꾸는 데 유용하다

출처: [prd-development skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md)

### 2.3 문제 정의와 story breakdown의 개별 품질 기준이 강하다

이 저장소는 큰 workflow 하나만 있는 것이 아니라, 각 중간 산출물에 대해 독립적인 기준을 둔다

- `problem-statement`: 사용자 관점의 문제 정의를 `I am / Trying to / But / Because / Which makes me feel` 구조로 강제
- `user-story`: Mike Cohn 형식과 Gherkin acceptance criteria를 결합
- `epic-breakdown-advisor`: Richard Lawrence의 9개 split pattern으로 epic을 작은 vertical slice로 분해

TCI에서는 이 점이 중요하다. 기능 설명을 PRD 한 장으로만 정리하면 여전히 구현 전달 품질이 떨어질 수 있는데, 이 저장소는 문제 정의, story 품질, split 논리까지 별도 프레임으로 보강한다

출처: [problem-statement skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/problem-statement/SKILL.md), [user-story skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/user-story/SKILL.md), [epic-breakdown-advisor skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/epic-breakdown-advisor/SKILL.md)

### 2.4 교육적 설계가 팀 내부 기준 정립에 유리하다

README와 최근 공지에서 이 저장소는 `pedagogic-first`, `ABC — Always Be Coaching`을 핵심 원칙으로 밝힌다. 각 스킬은 목적, 핵심 개념, 적용 단계, 예시, common pitfalls, references를 반복적으로 포함한다

이 특성은 TCI에 두 가지 의미가 있다

- 단순 산출물 생성보다 팀이 같은 사고법을 갖게 만드는 데 유리하다
- 반대로 당장 빠르게 문서만 뽑고 싶을 때는 다소 무겁게 느껴질 수 있다

출처: [README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md), [AGENTS.md](https://github.com/deanpeters/Product-Manager-Skills/blob/main/AGENTS.md), [CONTRIBUTING.md](https://github.com/deanpeters/Product-Manager-Skills/blob/main/CONTRIBUTING.md)

## 3. TCI 기준 장점

- `discover`, `write-prd`, `plan-roadmap` 같은 command 체인이 명확하다
- `problem-statement`, `user-story`, `epic-breakdown-advisor`처럼 중간 산출물의 품질 기준이 분리돼 있다
- PRD가 문제 정의, 성공 지표, out of scope, dependencies까지 포함해 handoff 품질이 높다
- story splitting과 acceptance criteria가 강해 구현 단위로 내리기 좋다
- README와 docs가 풍부해 팀 온보딩과 공통 기준 문서화에 유리하다
- Codex, ChatGPT, Claude 등 여러 환경에서 쓰는 방법을 별도 문서로 제공한다

출처: [README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md), [write-prd command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/write-prd.md), [prd-development skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md), [user-story skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/user-story/SKILL.md), [epic-breakdown-advisor skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/epic-breakdown-advisor/SKILL.md)

## 4. TCI 기준 리스크와 한계

- 기술 설계 산출물이 중심이 아니다
- 교육적 설명이 많아 빠른 경량 운영에는 무거울 수 있다
- 저장소 구조가 크고 문서량이 많아 필요한 부분만 선별하지 않으면 도입 범위가 넓어진다
- 공식 GitHub releases는 없다

조금 더 구체적으로 보면 아래와 같다

- `spec`, `tech plan`, `architecture`, `contracts`, `data model`에 해당하는 기술 문서 기본선은 확인되지 않았다
- PM 사고법을 가르치는 목적이 강해, 지금 당장 기능 설계 입력만 만들려는 상황에서는 설명량이 많다
- skill, command, docs, scripts, streamlit beta까지 포함해 저장소 범위가 넓다
- README에는 `v0.75`, `47 skills`, `6 command workflows` 같은 버전 표기가 있으나, GitHub releases 페이지에는 공개 릴리스가 없다
- 저장소 메타데이터 기준 생성일은 2026-02-05, 최신 push는 2026-04-02로 비교적 초기 단계다

출처: [README](https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md), [releases page](https://github.com/deanpeters/Product-Manager-Skills/releases), [latest commit](https://github.com/deanpeters/Product-Manager-Skills/commit/4aa4196c14873b84f5af7316e7f66328cb6dee4c), [repository root](https://github.com/deanpeters/Product-Manager-Skills)

## 5. 권장 도입 방식

### 권장 원칙

- 이 저장소를 기술 설계 프레임워크로 보지 않는다
- 문제 정의, PRD, backlog/story 품질 표준 레이어로 도입한다
- 전체 저장소를 한 번에 쓰기보다 `command + 핵심 skill`만 선별해 적용한다
- 기술 설계 문서는 `spec-kit`이나 BMAD 계열과 연결한다

### TCI 문서 체계와의 매핑

| TCI 목적 | Product-Manager-Skills 대응 | 비고 |
| --- | --- | --- |
| 문제 정의와 탐색 | `/discover`, `problem-framing-canvas`, `discovery-process` | 기능 착수 전 질문 정리 |
| 요구사항 문서화 | `/write-prd`, `prd-development`, `problem-statement` | PM 기준 PRD 작성 |
| 사용자 스토리화 | `user-story`, `user-story-splitting`, `epic-breakdown-advisor` | 구현 전달용 단위 |
| 로드맵과 우선순위 | `/plan-roadmap`, `prioritization-advisor`, `roadmap-planning` | 기능 묶음 관리 |
| acceptance 기준 정교화 | `user-story`의 Gherkin acceptance criteria | QA 전달 품질 향상 |
| 기술 설계 입력 작성 | 별도 프레임워크 필요 | spec-kit, codex-bmad-skills 등과 병행 권장 |

출처: [discover command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/discover.md), [write-prd command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/write-prd.md), [plan-roadmap command](https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/plan-roadmap.md), [prd-development skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md), [user-story skill](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/user-story/SKILL.md)

### 파일럿 권장 범위

TCI에서는 아래 성격의 기능에 먼저 붙여보는 편이 좋다

- 문제 정의가 아직 느슨한 기능
- 여러 사용자 시나리오와 edge case가 섞여 있는 기능
- epic을 작은 story로 쪼개는 데 팀 합의가 필요한 기능
- 기능 묶음을 로드맵 수준으로 정리해야 하는 영역

예시:

- 코드 저장소 연동 묶음 기능
- 문서-코드 추적 및 불일치 분석 기능
- 티켓 연동과 요구사항 흐름 관리 기능

권장 절차는 아래와 같다

1. `/discover` 또는 `problem-statement`로 문제와 사용자 맥락 정리
2. `/write-prd` 또는 `prd-development`로 요구사항 문서화
3. `user-story`와 `epic-breakdown-advisor`로 구현 전달 단위로 분해
4. 기능 묶음이면 `/plan-roadmap`으로 시퀀싱
5. 이후 기술 설계는 별도 설계 프레임워크로 넘긴다

## 6. 최종 판단

`deanpeters/Product-Manager-Skills`는 TCI에서 "기획을 더 나은 요구사항과 스토리 구조로 정제"하는 용도로 상당히 강한 후보다. 특히 아래 세 가지가 강점이다

- PM 사고법 자체를 가르치는 교육형 구조가 있다
- PRD와 story 품질 기준이 명확하다
- discovery에서 roadmap까지 이어지는 command 레이어가 있다

다만 이 저장소는 기술 설계 자체를 닫아주는 프레임워크가 아니다. 따라서 TCI에서의 현실적인 포지션은 아래와 같다

- PM 정제와 팀 표준화 레이어로는 유력
- 기술 설계 입력 생성은 별도 도구 필요
- `spec-kit`이나 BMAD 계열 앞단에 두면 가장 자연스럽다

정리하면 결론은 아래와 같다

- 교육성과 문서 품질은 강함
- 기술 설계 산출물은 약함
- PM 정제용 보완재로는 가치가 높음

## 7. 참고 링크

- 저장소: https://github.com/deanpeters/Product-Manager-Skills
- README: https://github.com/deanpeters/Product-Manager-Skills/blob/main/README.md
- Releases: https://github.com/deanpeters/Product-Manager-Skills/releases
- 최신 커밋 예시 `4aa4196`: https://github.com/deanpeters/Product-Manager-Skills/commit/4aa4196c14873b84f5af7316e7f66328cb6dee4c
- `discover` command: https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/discover.md
- `write-prd` command: https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/write-prd.md
- `plan-roadmap` command: https://github.com/deanpeters/Product-Manager-Skills/blob/main/commands/plan-roadmap.md
- `prd-development` skill: https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md
- `problem-statement` skill: https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/problem-statement/SKILL.md
- `user-story` skill: https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/user-story/SKILL.md
- `epic-breakdown-advisor` skill: https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/epic-breakdown-advisor/SKILL.md
