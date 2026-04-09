# phuryn/pm-skills 상세 조사

- 조사 대상: `phuryn/pm-skills`
- 조사 목적: TCI의 기능 기획을 설계 입력 직전의 PM 문서와 구조화된 실행 입력으로 끌어올릴 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 저장소, 공식 README, 공식 skill/command 문서, 공식 releases 페이지 중심

## 1. 한줄 결론

`phuryn/pm-skills`는 TCI가 가진 추상적 기능 아이디어를 `discovery → PRD → backlog/story → test scenario` 수준까지 정제하는 데 강한 PM 스킬 마켓플레이스다. 다만 `tech spec`, `architecture`, `data model`, `contracts` 같은 기술 설계 산출물은 명시적으로 제공하지 않으므로, "설계 입력 직전까지의 PM 정제 레이어"로 보는 편이 맞다

출처: [README](https://github.com/phuryn/pm-skills/blob/main/README.md), [discover command](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/commands/discover.md), [write-prd command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-prd.md), [write-stories command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-stories.md), [test-scenarios command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/test-scenarios.md)

참고: 아래 문서의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 discovery부터 execution까지 흐름이 이어진다

공식 README는 이 저장소를 `8 plugins`, `65 PM skills`, `36 chained workflows`로 소개한다. 구조도 `pm-product-discovery`, `pm-product-strategy`, `pm-execution`, `pm-market-research`, `pm-go-to-market` 등으로 나뉘어 있어, 기능 아이디어를 단발성 문서가 아니라 PM 전 과정의 산출물로 전개하기 쉽다

TCI 관점에서 중요한 점은 "기능 설명 한 줄"에서 바로 구현으로 넘어가지 않고, discovery와 strategy를 거쳐 execution 문서로 내려오는 레이어가 있다는 점이다

출처: [README](https://github.com/phuryn/pm-skills/blob/main/README.md), [repository root](https://github.com/phuryn/pm-skills)

### 2.2 명령 체인이 기획 정제 흐름을 명시한다

특히 아래 명령 체인이 TCI 목적과 잘 맞는다

- `/discover`: 아이디어 발산 → 가정 식별 → 가정 우선순위화 → 실험 설계 → discovery plan 생성
- `/write-prd`: 문제 정의와 맥락을 받아 8개 섹션 PRD 생성
- `/write-stories`: PRD나 기능 설명을 user stories, job stories, WWA로 분해
- `/test-scenarios`: user story나 feature spec을 QA 실행 가능한 시나리오로 변환

즉, 이 저장소는 "기능 설명을 더 좋은 문장으로 바꾼다" 수준이 아니라, 의사결정과 전달을 위한 문서 계층을 연속적으로 만든다

출처: [discover command](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/commands/discover.md), [write-prd command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-prd.md), [write-stories command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-stories.md), [test-scenarios command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/test-scenarios.md)

### 2.3 핵심 스킬이 PM 정제 산출물을 구체적으로 유도한다

개별 스킬 문서를 보면 산출물 형식이 비교적 선명하다

- `create-prd`: 8개 섹션 PRD 템플릿
- `prioritize-features`: impact, effort, risk, strategic alignment 기준 우선순위화
- `opportunity-solution-tree`: outcome → opportunities → solutions → experiments 구조화
- `test-scenarios`: 목표, 시작 조건, 사용자 역할, 단계별 액션, 기대 결과 기반 시나리오 작성

TCI에서 이 구조는 중요하다. 현재 기능 카탈로그를 "무엇을 만들까"에서 "어떤 문제를 풀고, 무엇을 우선하고, 어떤 스토리와 검증 조건으로 넘길까" 수준까지 끌어올리는 데 직접 도움이 된다

출처: [create-prd skill](https://github.com/phuryn/pm-skills/blob/main/pm-execution/skills/create-prd/SKILL.md), [prioritize-features skill](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/skills/prioritize-features/SKILL.md), [opportunity-solution-tree skill](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/skills/opportunity-solution-tree/SKILL.md), [test-scenarios skill](https://github.com/phuryn/pm-skills/blob/main/pm-execution/skills/test-scenarios/SKILL.md)

### 2.4 Codex 환경에서는 skills 재사용이 가능하다

README는 Claude Code와 Cowork를 1차 대상으로 두지만, 다른 AI 도구에서는 `skills/*/SKILL.md`를 복사해 재사용할 수 있다고 설명한다. 표에는 Codex CLI도 포함돼 있다

이는 TCI에 실질적인 의미가 있다. 명령 체인은 Claude 중심이지만, 핵심 지식과 문서 구조는 Codex 환경으로도 옮길 수 있다. 즉, 전체 마켓플레이스를 그대로 쓰기보다 필요한 스킬을 선별 이식하는 전략이 가능하다

출처: [README](https://github.com/phuryn/pm-skills/blob/main/README.md)

## 3. TCI 기준 장점

- discovery, strategy, execution이 분리돼 있어 기능 아이디어를 단계적으로 정제하기 좋다
- `/discover → /write-prd → /write-stories → /test-scenarios` 흐름이 TCI의 기획 정제 목적과 직접 맞닿아 있다
- `prioritize-features`, `opportunity-solution-tree`, `create-prd` 같은 스킬이 문제 정의와 우선순위화를 강제한다
- user story, job story, WWA, test scenario까지 내려가므로 구현 전 전달 품질이 높아진다
- Codex CLI에서도 skills-only 방식으로 재사용 가능하다
- 시장 조사, GTM, metrics까지 포함돼 있어 기능 단건보다 상위 맥락을 보강하기 쉽다

출처: [README](https://github.com/phuryn/pm-skills/blob/main/README.md), [discover command](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/commands/discover.md), [write-prd command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-prd.md), [write-stories command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-stories.md)

## 4. TCI 기준 리스크와 한계

- 기술 설계 산출물이 약하다
- Claude 전용 command UX 의존도가 높다
- 저장소가 아직 초기 단계라 운영 안정성 판단을 보수적으로 해야 한다
- PM 범위가 넓어 "단일 기능 설계 입력 문서화"만 목표일 때는 과할 수 있다

조금 더 구체적으로 보면 아래와 같다

- `tech spec`, `architecture`, `data model`, `contracts`에 해당하는 명시적 템플릿은 확인되지 않았다
- README는 다른 도구에서 skills는 재사용 가능하다고 밝히지만, `/discover`, `/write-prd` 같은 slash command는 Claude 특화다
- GitHub releases 페이지 기준 현재 공개 릴리스가 없다
- GitHub 메타데이터 기준 저장소는 2026-03-01 생성, 최신 push는 2026-03-09이며 아직 변화 주기가 빠른 초기 프로젝트로 보인다
- README 상단은 `65 PM skills and 36 chained workflows`라고 설명하지만, 저장소 설명은 `100+ agentic skills`라고 적혀 있어 문서 수치가 완전히 정합적이지는 않다

출처: [README](https://github.com/phuryn/pm-skills/blob/main/README.md), [releases page](https://github.com/phuryn/pm-skills/releases), [latest commit](https://github.com/phuryn/pm-skills/commit/36ccefdc6c2e00d7c0c12cb0a52bf93e8ec50da4), [repository root](https://github.com/phuryn/pm-skills)

## 5. 권장 도입 방식

### 권장 원칙

- `phuryn/pm-skills`를 단독 설계 프레임워크로 보지 않는다
- discovery와 PM 문서화 레이어에 한정해 도입한다
- Codex 환경에서는 slash command보다 개별 `SKILL.md` 이식과 재조합을 우선한다
- 기술 설계 산출물은 별도 템플릿이나 다른 후보와 연결한다

### TCI 문서 체계와의 매핑

| TCI 목적 | pm-skills 대응 | 비고 |
| --- | --- | --- |
| 아이디어 발산과 문제 정의 | `/discover`, `brainstorm-*`, `identify-assumptions-*` | 설계 전 논점 정리 |
| 기능 우선순위 정제 | `prioritize-features`, `analyze-feature-requests` | backlog 전 단계 정리 |
| 요구사항 문서화 | `/write-prd`, `create-prd` | PM 기준 PRD 생성 |
| 스토리 단위 분해 | `/write-stories`, `user-stories`, `job-stories`, `wwas` | 구현 전달용 문서 |
| 검증 기준 정리 | `/test-scenarios`, `test-scenarios` | QA 및 acceptance 입력 |
| 기술 설계 입력 작성 | 별도 템플릿 필요 | spec-kit 또는 BMAD 계열과 병행 권장 |

출처: [discover command](https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/commands/discover.md), [write-prd command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-prd.md), [write-stories command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-stories.md), [test-scenarios command](https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/test-scenarios.md)

### 파일럿 권장 범위

TCI에서는 아래 성격의 기능에 먼저 붙여보는 편이 좋다

- 사용자 문제와 가치 정의가 아직 느슨한 기능
- 기능 후보가 많아 우선순위 판단이 필요한 영역
- PRD와 story가 먼저 닫혀야 기술 설계가 쉬워지는 기능
- 설계 전에 acceptance와 검증 조건을 미리 정리해야 하는 기능

예시:

- 코드 저장소 연동 기능 묶음
- 문서-코드 추적 기능
- 티켓 시스템과 요구사항 연결 기능

권장 절차는 아래와 같다

1. `/discover` 수준의 discovery plan 작성
2. `prioritize-features` 또는 `opportunity-solution-tree`로 문제와 기회 구조화
3. `/write-prd`로 기능 범위와 성공 기준 문서화
4. `/write-stories`로 구현 전달 단위 분해
5. `/test-scenarios`로 검증 시나리오 작성
6. 이후 기술 설계는 `github/spec-kit` 또는 BMAD 계열 프레임워크로 넘긴다

## 6. 최종 판단

`phuryn/pm-skills`는 "기획을 설계로 구체화"라는 목표 중에서도 특히 `설계 이전의 PM 정제 단계`에 강한 후보다. 강점은 세 가지다

- discovery와 execution 사이에 문서 계층이 분명하다
- PRD, stories, test scenarios까지 이어지는 전달 구조가 좋다
- Codex에서도 skills-only 방식으로 일부 재사용할 수 있다

반면 기술 설계 자체를 닫아주는 프레임워크는 아니다. 따라서 TCI에서는 단독 채택보다 아래처럼 보는 편이 맞다

- discovery와 요구사항 정제 레이어로는 유력
- 기술 설계 산출물 생성은 별도 도구 필요
- `spec-kit`이나 BMAD 계열과 조합할 때 가치가 가장 크다

## 7. 참고 링크

- 저장소: https://github.com/phuryn/pm-skills
- README: https://github.com/phuryn/pm-skills/blob/main/README.md
- Releases: https://github.com/phuryn/pm-skills/releases
- 최신 커밋 예시 `36ccefd`: https://github.com/phuryn/pm-skills/commit/36ccefdc6c2e00d7c0c12cb0a52bf93e8ec50da4
- `discover` command: https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/commands/discover.md
- `write-prd` command: https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-prd.md
- `write-stories` command: https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/write-stories.md
- `test-scenarios` command: https://github.com/phuryn/pm-skills/blob/main/pm-execution/commands/test-scenarios.md
- `create-prd` skill: https://github.com/phuryn/pm-skills/blob/main/pm-execution/skills/create-prd/SKILL.md
- `prioritize-features` skill: https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/skills/prioritize-features/SKILL.md
- `opportunity-solution-tree` skill: https://github.com/phuryn/pm-skills/blob/main/pm-product-discovery/skills/opportunity-solution-tree/SKILL.md
- `test-scenarios` skill: https://github.com/phuryn/pm-skills/blob/main/pm-execution/skills/test-scenarios/SKILL.md
