# Spec Kit 단계별 산출물 설명

- 작성일: 2026-04-14
- 대상: `github/spec-kit`을 `Codex CLI` 기준으로 사용할 때 생성되는 단계별 산출물
- 목적: 각 명령어가 실제로 무엇을 만들고, 그 산출물이 어떤 역할을 하는지 예시와 함께 설명

## 한줄 요약

Spec Kit의 산출물은 단순 문서 모음이 아니다. 프로젝트 운영 원칙을 정하는 `constitution`부터 시작해서, 기능 요구사항을 고정하는 `spec`, 모호한 부분을 해소하는 `clarify`, 기술 설계를 준비하는 `plan`, 실행 단위로 쪼개는 `tasks`, 실제 구현으로 이어지는 `implement`까지, 다음 단계로 넘기는 문서 묶음이 차례대로 만들어진다고 이해하면 된다.

Codex CLI에서는 공식 문서의 `/speckit.*`를 보통 `$speckit-*`로 바꿔서 보면 된다.

| 공식 문서 표기 | Codex CLI 기준 |
| --- | --- |
| `/speckit.constitution` | `$speckit-constitution` |
| `/speckit.specify` | `$speckit-specify` |
| `/speckit.clarify` | `$speckit-clarify` |
| `/speckit.checklist` | `$speckit-checklist` |
| `/speckit.plan` | `$speckit-plan` |
| `/speckit.tasks` | `$speckit-tasks` |
| `/speckit.analyze` | `$speckit-analyze` |
| `/speckit.implement` | `$speckit-implement` |

## 먼저 알아둘 점

### Spec Kit이란 무엇인가

Spec Kit은 "기능 설명을 바로 코드로 옮기기 전에, 요구사항과 설계 문서를 먼저 정리하자"는 흐름을 도와주는 도구이자 작업 방식이다. 즉, 아이디어나 기획 메모를 바로 구현하는 대신, 먼저 기능 명세와 기술 계획을 문서로 고정한 뒤 구현으로 넘어가게 만든다.

### SDD란 무엇인가

SDD는 `Spec-Driven Development`의 줄임말이다. 말 그대로 구현보다 `spec(명세)`를 먼저 두는 개발 방식이다. 여기서 말하는 명세는 단순한 회의 메모가 아니라, "무엇을 만들어야 하는지", "성공 기준이 무엇인지", "어떤 설계가 필요한지"를 다른 사람이 읽어도 이해할 수 있게 정리한 문서를 뜻한다.

### 이 문서에서 말하는 산출물이란 무엇인가

이 문서에서 `산출물`은 각 단계가 끝났을 때 실제로 남는 파일이나 폴더를 뜻한다. 예를 들어 `spec.md`, `plan.md`, `tasks.md`, `contracts/` 같은 것들이 모두 산출물이다. 즉, "대화 내용"이 아니라 Git에 남겨서 다음 사람에게 넘길 수 있는 결과물이라고 보면 된다.

### 왜 코드보다 명세를 먼저 만드는가

기획 문서만 보고 바로 구현에 들어가면, 범위가 중간에 바뀌거나, 성공 기준이 흐릿하거나, 외부 연동 방식이 뒤늦게 꼬이는 경우가 많다. Spec Kit은 이 문제를 줄이기 위해 `요구사항 정리 → 빈칸 메우기 → 기술 설계 → 작업 분해`를 먼저 하게 만든다. 그래서 Spec Kit의 핵심 가치는 "문서를 많이 만든다"가 아니라 "구현 전에 생각해야 할 것을 문서로 분명히 남긴다"에 있다.

## 전체 흐름 한눈에 보기

처음 쓰는 사람은 각 문서를 따로 보지 말고 아래 순서로 이해하는 것이 가장 쉽다.

| 순서 | 단계 | 필수 여부 | 입력 | 대표 산출물 | 다음 단계로 넘기는 것 |
| --- | --- | --- | --- | --- | --- |
| 1 | `specify init` | 필수 | 빈 프로젝트 또는 기존 레포 | `.specify/`, `specs/` | Spec Kit 작업장 |
| 2 | `constitution` | 권장 | 프로젝트 운영 원칙 초안 | `constitution.md` | 프로젝트 공통 규칙 |
| 3 | `specify` | 필수 | 기능 설명, 기획 메모 | `spec.md`, `checklists/requirements.md` | 기능 요구사항 초안 |
| 4 | `clarify` | 강력 권장 | 초안 `spec.md` | 갱신된 `spec.md` | 모호성이 줄어든 명세 |
| 5 | `plan` | 필수 | 정리된 `spec.md`, `constitution.md` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | 기술 설계 입력 |
| 6 | `tasks` | 필수 | `spec.md`, `plan` 산출물들 | `tasks.md` | 실행 가능한 작업 목록 |
| 7 | `analyze` | 선택이지만 권장 | `spec.md`, `plan.md`, `tasks.md` | 분석 리포트 | 문서 간 충돌/누락 점검 결과 |
| 8 | `implement` | 상황에 따라 | 위 단계 전체 산출물 | 코드, 테스트, 문서 반영 | 실제 구현 결과 |

### 헷갈리기 쉬운 점

- `checklists/requirements.md`는 보통 `specify` 단계에서 함께 만들어지는 기본 체크리스트다.
- `$speckit-checklist`는 그 이후에 필요하면 추가로 만드는 보조 체크리스트다.
- 즉, `requirements.md`는 "기본 검토표", `security.md`나 `ux.md` 같은 파일은 "추가 관점 검토표"라고 보면 된다.

### 처음에는 어디까지 쓰면 되는가

처음부터 모든 단계를 다 쓰지 않아도 된다. 실무에서는 보통 `specify → clarify → plan → tasks`까지만 제대로 써도 큰 도움이 된다. `analyze`는 문서 품질을 한 번 더 점검할 때, `implement`는 실제 구현 단계까지 이어갈 때 사용하면 된다.

## 용어 빠르게 보기

- `constitution`: 프로젝트 운영 원칙 문서
- `spec`: 기능 요구사항 문서
- `clarify`: 모호한 부분을 질문과 답변으로 정리하는 단계
- `plan`: 기술 설계를 시작하기 위한 준비 단계
- `contracts`: 외부 연동의 입출력 약속을 적은 문서
- `traceability`: 요구사항, 작업, 구현 결과를 서로 연결해 추적할 수 있는 상태
- `backlog`: 나중에 구현하거나 검토할 작업 목록
- `LLM`: 대규모 언어 모델. 여기서는 Codex 같은 AI 코딩 도구를 뜻함

## 이 문서에서 예시를 읽는 방법

아래 예시는 한국어 중심으로 적었다. 다만 실제 파일명, 폴더명, 외부 도구 이름은 영어로 남을 수 있다. 실제 팀 문서는 한국어로 작성해도 된다. 중요한 것은 언어가 아니라, 각 문서가 어떤 역할을 하며 다음 단계에 무엇을 넘겨주는지가 분명한지다.

## 1. 초기화: `specify init`

### 주요 산출물

- `.specify/`
- `specs/`
- `.agents/skills/speckit-*` (Codex CLI에서 `--ai-skills`로 초기화한 경우)

### 이 산출물의 의미

이 단계는 기능 문서를 만드는 단계가 아니라, Spec Kit가 앞으로 동작할 작업장을 세팅하는 단계다.

- `.specify/`는 템플릿, 스크립트, 메모리, 확장 설정이 들어가는 시스템 디렉터리다.
- `specs/`는 기능별 산출물이 실제로 쌓이는 작업 디렉터리다.
- `.agents/skills/speckit-*`는 Codex가 각 단계를 호출할 수 있게 해주는 진입점이다.

### 알아둘 점

- `specify init` 자체는 공식 Spec Kit 초기화 단계다.
- `.agents/skills/`는 Codex CLI에서 Spec Kit를 skill 형태로 쓰기 위해 추가되는 로컬 진입점이다.
- 즉, `specs/`와 `.specify/`는 Spec Kit의 일반 구조이고, `.agents/skills/`는 Codex 환경에서 더해지는 사용 방식이라고 보면 된다.

| 구분 | 무엇인가 | 꼭 필요한가 |
| --- | --- | --- |
| 공식 Spec Kit 기본 구조 | `.specify/`, `specs/` | 예 |
| Codex CLI 추가 구조 | `.agents/skills/speckit-*` | Codex에서 skill 방식으로 쓸 때만 필요 |
| TCI 로컬 사용 방식 | Codex에서 `$speckit-*`로 호출 | 이 프로젝트에서는 사실상 권장 |

### 예시

```text
.specify/
  memory/
  templates/
  scripts/

specs/
  001-github-traceability/

.agents/skills/
  speckit-specify/
  speckit-plan/
  speckit-tasks/
```

이 구조가 생기면, 그 다음부터는 각 기능마다 `specs/001-.../` 아래로 문서가 내려간다.

## 2. 프로젝트 원칙 정의: `$speckit-constitution`

### 주요 산출물

- `.specify/memory/constitution.md`

### 이 산출물의 의미

이 파일은 개별 기능 문서가 아니라 프로젝트 헌법이다. 앞으로 생성되는 `spec.md`, `plan.md`, `tasks.md`가 어떤 기준을 따라야 하는지 정하는 상위 규칙이다.

예를 들면 아래 같은 원칙이 들어간다.

- 문서 우선 개발
- 구현보다 명세와 계획 우선
- 외부 시스템 연동은 계약 문서 필수
- 변경 이력 추적 가능해야 함
- 테스트 또는 검증 절차 명시

즉, constitution은 "무엇을 만들까"보다 "이 프로젝트는 어떤 방식으로 일할까"를 고정하는 문서다.

### 예시

```md
## 원칙 1: 문서 우선 개발
모든 기능 작업은 반드시 명세 문서와 계획 문서에서 시작해야 한다.

## 원칙 2: 추적 가능한 변경 이력
모든 요구사항, 작업, 구현 변경은 반드시 출처 문서나 결정 이력과 연결되어야 한다.

## 원칙 3: 외부 연동 계약 명시
외부 시스템 연동은 반드시 구현 전에 입력과 출력 계약을 정의해야 한다.
```

### 실무 해석

나중에 `plan` 단계에서 GitHub API를 붙이려 할 때 `contracts/`가 빠져 있으면, 그건 단순 누락이 아니라 constitution 위반으로 볼 수 있다.

## 3. 기능 명세 작성: `$speckit-specify`

### 주요 산출물

- `specs/<feature>/spec.md`
- `specs/<feature>/checklists/requirements.md`

### 이 산출물의 의미

`spec.md`는 기능 요구사항 계약서다. 여기서 핵심은 구현 방법이 아니라 사용자 가치, 기능 요구사항, 성공 기준, 범위를 명확히 고정하는 것이다.

Spec Kit은 이 단계에서 기술 스택이나 API 구조 같은 구현 상세를 넣지 않도록 강하게 유도한다. 즉, `spec.md`는 "어떻게 만들까"가 아니라 "무엇을 왜 만들까"를 적는 문서다.

### 예시

가상의 기능: `기획 문서를 GitHub 이슈 초안으로 변환`

```md
# 기능 명세: 기획 문서 기반 GitHub 이슈 초안 생성

## 사용자 시나리오
- PM이 기획 문서를 업로드하면 구조화된 GitHub 이슈 초안 목록을 받는다.
- 검토자는 생성된 초안을 확인하고 수정한 뒤 팀 작업 목록으로 넘길지 판단한다.

## 기능 요구사항
- FR-001: 시스템은 기획 문서를 파싱해 작업 후보를 식별해야 한다.
- FR-002: 시스템은 각 작업 후보에 대해 제목, 설명, 수용 기준이 포함된 이슈 초안을 생성해야 한다.
- FR-003: 시스템은 내보내기 전에 검토자가 초안을 수정할 수 있어야 한다.

## 성공 기준
- SC-001: PM은 기획 문서 업로드 후 10분 이내에 이슈 초안 목록을 확인할 수 있어야 한다.
- SC-002: 생성된 이슈 초안의 90% 이상에는 수용 기준이 포함되어야 한다.

## 예외 상황
- 입력 문서에 같은 작업이 중복으로 적혀 있을 수 있다.
- 입력 문서에 로드맵 수준 항목과 구현 세부 항목이 섞여 있을 수 있다.
```

같은 예시를 한국어로 아주 짧게 쓰면 아래처럼 이해하면 된다.

```md
## 사용자 시나리오
- PM이 기획 문서를 올리면 이슈 초안 목록을 받는다.

## 기능 요구사항
- 시스템은 기획 문서에서 작업 후보를 추출해야 한다.
- 시스템은 각 작업 후보에 대해 제목, 설명, 수용 기준이 포함된 이슈 초안을 만들어야 한다.

## 성공 기준
- PM은 10분 안에 이슈 초안을 확인할 수 있어야 한다.
```

### 실무 해석

이 문서가 잘 써져 있으면 개발자, PM, QA가 같은 기능을 같은 뜻으로 이해할 수 있다. 반대로 이 문서가 모호하면 이후 `plan`, `tasks`, `implement`가 전부 흔들린다.

## 4. Spec 품질 점검: `checklists/requirements.md`

### 주요 산출물

- `specs/<feature>/checklists/requirements.md`

### 이 산출물의 의미

이 체크리스트는 구현 테스트가 아니라 요구사항 검토표다. 즉, "코드가 동작하나?"를 보는 것이 아니라 "이 spec이 planning 단계로 넘어갈 만큼 잘 정의되어 있나?"를 확인한다.

이 파일은 보통 `$speckit-specify` 단계에서 함께 만들어진다. 즉, 완전히 별도 단계라기보다 `specify`가 만든 기본 점검표라고 이해하는 편이 정확하다.

### 예시

```md
# 명세 품질 점검표: 기획 문서 기반 GitHub 이슈 초안 생성

## 내용 품질
- [ ] 언어, 프레임워크, API 같은 구현 세부가 들어가 있지 않다
- [ ] 사용자 가치와 업무 목적 중심으로 작성되어 있다
- [ ] 비개발자도 읽고 이해할 수 있게 작성되어 있다

## 요구사항 완성도
- [ ] 요구사항이 모호하지 않고 검토 가능하다
- [ ] 성공 기준이 수치나 관찰 가능한 결과로 표현되어 있다
- [ ] 주요 수용 시나리오가 빠짐없이 적혀 있다

## 기능 준비 상태
- [ ] 각 기능 요구사항에 확인 가능한 수용 기준이 있다
- [ ] 사용자 시나리오가 핵심 흐름을 다루고 있다
- [ ] 명세에 구현 세부가 새어 들어오지 않았다
```

### 실무 해석

이 파일은 설계 착수 전 통과 기준이다. 예를 들어 성공 기준이 모호하거나, 요구사항이 테스트 불가능한 문장이라면 `plan`으로 넘어가기 전에 수정해야 한다.

## 5. 모호성 해소: `$speckit-clarify`

### 주요 산출물

- 새 파일을 만들기보다 기존 `spec.md`를 갱신
- 보통 `## Clarifications` 섹션 추가

### 이 산출물의 의미

`clarify`는 spec의 빈칸을 메우는 단계다. 질문을 던지고, 그 답을 다시 spec 안으로 반영해서 "생각나는 대로 적은 기능 설명"을 "계획 가능한 기능 명세"로 바꾼다.

로컬 skill 정의 기준으로 아래 패턴이 들어간다.

- `## Clarifications`
- `### Session YYYY-MM-DD`
- `- Q: ... → A: ...`

그리고 질문/답변 로그만 남기는 것이 아니라, 관련 요구사항 섹션도 같이 업데이트한다.

### 예시

```md
## 명확화 기록

### 세션 2026-04-14
- Q: 생성 결과를 GitHub에 바로 게시하나, 초안만 만들까? → A: 초안만 생성
- Q: 누가 최종 승인 권한을 가지나? → A: PM 리뷰어
```

이 답변을 반영해 기존 요구사항이 아래처럼 바뀔 수 있다.

```md
- FR-004: 시스템은 GitHub에 바로 게시하지 않고 이슈 초안만 내보내야 한다.
- FR-005: 시스템은 최종 내보내기 전에 PM 리뷰어의 명시적 승인을 받아야 한다.
```

### 실무 해석

`clarify`의 가치는 질문 목록 자체보다, 그 결과가 `spec.md` 본문에 반영된다는 데 있다. 즉, "회의 메모"가 아니라 "명세의 수정 이력"이 된다.

## 6. 추가 관점 체크리스트: `$speckit-checklist`

### 주요 산출물

- `specs/<feature>/checklists/security.md`
- `specs/<feature>/checklists/ux.md`
- `specs/<feature>/checklists/api.md`

### 이 산출물의 의미

이 단계는 선택 사항이지만 실무적으로 매우 유용하다. 기본 `requirements.md`가 전체 검토 기준이라면, 이 단계는 특정 관점에서 spec을 더 깊게 점검하는 보조 체크리스트를 만든다.

즉, 관계를 단순하게 정리하면 아래와 같다.

- `requirements.md`: `specify`가 기본으로 만드는 전체 검토표
- `security.md`, `ux.md`, `api.md`: 필요할 때 추가하는 관점별 검토표

### 예시

`security.md`

```md
## 접근 권한
- [ ] 누가 초안을 생성할 수 있는지 명세에 적혀 있는가
- [ ] 누가 내보내기를 승인할 수 있는지 명세에 적혀 있는가

## 데이터 처리
- [ ] 업로드되는 기획 문서에 민감 정보가 포함될 수 있는지 적혀 있는가
- [ ] 보관 기간이나 삭제 기준이 적혀 있는가
```

### 실무 해석

이 파일은 아직 코드 검토 문서가 아니다. 여전히 요구사항 검토 문서다. 단지 시선을 보안, UX, 운영, API 관점으로 좁혀서 보는 것이다.

## 7. 기술 계획 수립: `$speckit-plan`

### 주요 산출물

- `specs/<feature>/plan.md`
- `specs/<feature>/research.md`
- `specs/<feature>/data-model.md`
- `specs/<feature>/contracts/`
- `specs/<feature>/quickstart.md`

### 이 산출물의 의미

이 단계는 Spec Kit에서 가장 중요한 기술 설계 준비 단계다. `spec.md`가 문제와 요구사항을 고정했다면, `plan`은 이제 그것을 실제 시스템 설계로 바꾸는 단계다.

먼저 다섯 산출물의 역할을 한 줄로 보면 아래와 같다.

| 산출물 | 무엇을 적는가 | 무엇은 적지 않는가 |
| --- | --- | --- |
| `plan.md` | 전체 설계 방향, 제약, 검증 포인트 | 세부 기술 선택의 긴 비교 과정 |
| `research.md` | 왜 이 선택을 했는지, 어떤 대안을 검토했는지 | 전체 시스템 구조 설명 |
| `data-model.md` | 핵심 데이터 개체와 관계 | API 세부 요청/응답 형식 |
| `contracts/` | 외부 연동 입출력 약속 | 사용자 검증 절차 |
| `quickstart.md` | 사람이 따라 해보는 검증 흐름 | 설계 선택의 이유 |

#### `plan.md`

전체 기술 접근을 적는 중심 문서다.

예시:

```md
## 기술 맥락
- 서비스 형태: 내부용 웹 도구
- 주요 연동 대상: GitHub Issues API
- 주요 위험: 형식이 제각각인 기획 문서가 중복 이슈 초안을 만들 수 있음

## 원칙 점검
- 외부 연동에는 계약 문서가 필요함
- 원본 문서와 이슈 초안 사이의 추적 링크가 필요함
```

의미: 설계 방향, 제약, 검증 포인트를 한 문서에 묶는다.

#### `research.md`

미결정 기술 선택과 그 근거를 남기는 문서다.

예시:

```md
## 결정: 1차 버전은 JSON 기반 이슈 초안 내보내기를 사용한다

### 이유
- 바로 게시하는 방식보다 운영 위험이 낮다
- PM과 엔지니어링 매니저가 검토하기 쉽다

### 검토한 대안
- GitHub에 바로 이슈 생성
- CSV 내보내기
```

의미: 왜 이런 설계를 택했는지 나중에 다시 확인할 수 있게 만든다.

#### `data-model.md`

기능에 필요한 핵심 엔티티와 관계를 정의한다.

예시:

```md
## 주요 엔티티

### 요구사항 문서
- 문서 ID
- 원본 경로
- 업로드한 사람
- 생성 시각

### 이슈 초안
- 초안 ID
- 제목
- 설명
- 수용 기준
- 검토 상태

### 추적 링크
- 요구사항 문서 ID
- 이슈 초안 ID
- 원본 섹션 위치
```

의미: 구현 전 데이터 구조와 개념 모델을 정리한다.

#### `contracts(연동 계약 문서 모음)`

외부 시스템 또는 외부에 노출되는 인터페이스 계약을 정리한다.

예시:

```text
contracts/
  draft-issue-export.openapi.yaml
  webhook-input.schema.json
```

예시 내용:

```yaml
paths:
  /draft-issues/export:
    post:
      summary: 검토가 끝난 이슈 초안을 내보낸다
```

의미: 외부 시스템과 주고받는 약속을 문서로 고정한다.

#### `quickstart.md`

이 기능이 정상적으로 동작하는지 사람이 따라가며 검증할 수 있는 사용 시나리오다.

예시:

```md
1. 기획 문서를 업로드한다
2. 추출된 작업 후보를 검토한다
3. 이슈 초안을 수정한다
4. 검토가 끝난 초안을 내보낸다
5. 원본 문서와 이슈 초안의 연결 정보가 유지됐는지 확인한다
```

의미: 개발자, QA, 리뷰어가 같은 검증 흐름을 따라가게 만든다.

## 8. 실행 작업 분해: `$speckit-tasks`

### 주요 산출물

- `specs/<feature>/tasks.md`

### 이 산출물의 의미

`tasks.md`는 설계를 바로 실행 가능한 작업 단위로 분해한 문서다. 중요한 점은 단순 TODO 목록이 아니라, 사용자 스토리별로 독립 구현과 독립 검증이 가능하도록 정렬된 작업 계획이라는 점이다.

로컬 skill 정의 기준으로 보통 아래 구조를 가진다.

- Phase 1: 준비
- Phase 2: 공통 기반
- Phase 3+: 사용자 시나리오별 구현 단계
- 마지막 단계: 마무리와 공통 정리

여기서 `Phase`는 작업 단계를 뜻하고, `사용자 스토리`는 사용자 관점에서 묶은 기능 단위를 뜻한다.

왜 이렇게 나누냐면, 먼저 공통 기반을 만들고, 그 다음 사용자 시나리오별 기능을 붙이고, 마지막에 로그나 문서 업데이트 같은 공통 정리를 하기 위해서다.

### 예시

```md
## Phase 1: 준비
- [ ] T001 `src/features/draft_issues/` 아래 기능 기본 구조를 만든다
- [ ] T002 `tests/integration/` 아래 통합 테스트 기본 환경을 추가한다

## Phase 2: 공통 기반
- [ ] T003 `src/domain/`에 이슈 초안과 추적 링크 모델을 정의한다
- [ ] T004 `src/parsing/`에 문서 파싱 인터페이스를 추가한다

## Phase 3: 사용자 스토리 1 - 이슈 초안 생성
- [ ] T005 [US1] 기획 문서를 작업 후보 목록으로 파싱한다
- [ ] T006 [US1] 각 작업 후보에 대해 이슈 초안 제목과 설명을 만든다
- [ ] T007 [US1] 초안 생성 흐름에 대한 통합 테스트를 추가한다

## Phase 4: 사용자 스토리 2 - 검토자 승인
- [ ] T008 [US2] 검토 상태 전이 규칙을 추가한다
- [ ] T009 [US2] 검토자가 수정하고 승인하는 기능을 만든다
- [ ] T010 [US2] 승인 흐름 테스트를 추가한다

## 마지막 단계: 마무리
- [ ] T011 내보내기 이벤트에 대한 감사 로그를 남긴다
- [ ] T012 사용자 문서를 업데이트한다
```

### 실무 해석

이 파일은 사람이 읽는 계획표이면서, 동시에 LLM이나 구현자가 바로 따라갈 수 있는 작업 목록 역할도 한다. 좋은 `tasks.md`는 추가 설명 없이도 다음 행동이 보이게 만든다.

## 9. 교차 검토: `$speckit-analyze`

### 주요 산출물

- 보통 새 문서 파일보다는 분석 리포트 출력
- 대상은 `spec.md`, `plan.md`, `tasks.md`

### 이 산출물의 의미

이 단계는 코딩 전에 문서 세트가 서로 잘 맞물리는지 점검하는 단계다. 즉, 각 문서가 개별적으로 그럴듯한지만 보는 것이 아니라, 서로 맞물리는지, 충돌하거나 빠진 부분이 없는지 점검한다.

예를 들면 아래 같은 이슈를 잡아낼 수 있다.

- `spec.md`에는 승인 절차가 있는데 `tasks.md`에는 승인 관련 작업이 없음
- `plan.md`에는 외부 연동 계약 문서가 필요하다고 했는데 `contracts/`가 비어 있음
- constitution은 추적성을 요구하는데 `data-model.md`에 추적 링크 개념이 없음

### 예시

```text
치명적
- spec에는 검토자 승인이 필요하다고 되어 있는데, tasks.md에는 승인 흐름 작업이 없다.

중간
- plan.md에는 감사 로그가 언급되어 있지만, quickstart.md에는 로그 확인 절차가 없다.

낮음
- 성공 기준에는 "10분 이내"가 있는데, quickstart.md에는 시간을 어떻게 검증할지 적혀 있지 않다.
```

### 실무 해석

`analyze`는 새 설계 문서를 만드는 단계가 아니라, 설계 문서 세트가 구현에 들어가도 되는지 마지막으로 검수하는 단계다.

## 10. 구현 실행: `$speckit-implement`

### 주요 산출물

- 실제 코드
- 테스트 코드
- 필요한 ignore 파일 보완
- 구현 결과에 따른 문서 업데이트

### 이 산출물의 의미

앞 단계들의 산출물이 모두 "코딩 전 문서 패키지"였다면, `implement`는 그 계획을 따라 실제 결과물을 만드는 단계다.

로컬 skill 정의 기준으로 `implement`는 아래 문서들을 읽고 구현을 진행한다.

- `tasks.md`
- `plan.md`
- `data-model.md`
- `contracts/`
- `research.md`
- `quickstart.md`

즉, 이 단계는 새롭게 방향을 정하기보다 이미 정리된 문서를 실행하는 단계다.

### 알아둘 점

`implement`를 보면 처음 쓰는 사람은 "그럼 이 명령이 자동으로 코드를 다 만들어주나?"라고 생각하기 쉽다. 실제로는 문서를 바탕으로 구현을 진행하는 단계라고 이해하는 편이 정확하다. 자동화 수준은 사용하는 환경, 에이전트 설정, 팀의 작업 방식에 따라 달라질 수 있다.

### 예시

```text
src/features/draft_issues/초안_생성.py
src/features/draft_issues/검토_승인.py
src/domain/이슈_초안.py
tests/integration/test_초안_생성.py
tests/integration/test_검토자_승인.py
contracts/draft-issue-export.openapi.yaml
```

### 실무 해석

`implement`는 Spec Kit 흐름의 끝이라기보다, 앞선 문서 산출물들이 실제로 쓸모 있었는지를 증명하는 단계다. 만약 이 단계에서 자꾸 막힌다면 문제는 구현 능력보다 앞 단계 문서 품질일 가능성이 크다.

## 단계별 산출물 요약

| 단계 | 대표 산출물 | 의미 |
| --- | --- | --- |
| `specify init` | `.specify/`, `specs/`, `.agents/skills/` | Spec Kit 작업장과 도구 설치 |
| `constitution` | `.specify/memory/constitution.md` | 프로젝트 운영 원칙 |
| `specify` | `spec.md` | 기능 요구사항 계약서 |
| `specify` | `checklists/requirements.md` | spec 기본 검토 기준 |
| `clarify` | 갱신된 `spec.md` | 모호성 해소와 명세 보강 |
| `checklist` | `checklists/*.md` | 특정 관점의 요구사항 점검 |
| `plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` | 기술 설계 입력 패키지 |
| `tasks` | `tasks.md` | 실행 가능한 작업 분해 |
| `analyze` | 분석 리포트 | 문서 간 충돌과 누락 점검 |
| `implement` | 코드, 테스트, 문서 반영 | 실제 구현 결과물 |

## 일반적으로 이렇게 이해하면 된다

Spec Kit을 처음 접하는 사람이라면 각 산출물을 아래처럼 기억하면 된다.

- `constitution.md`: 이 프로젝트가 어떤 원칙으로 일할지 정하는 문서
- `spec.md`: 무엇을 만들지 정리한 기능 요구사항 문서
- `clarify` 반영본: 빠진 질문에 답해 더 분명해진 명세
- `plan` 산출물 묶음: 어떻게 설계할지 정리한 문서 묶음
- `tasks.md`: 실제 구현과 검토를 위해 쪼갠 작업 목록
- `analyze`: 문서끼리 충돌이나 누락이 없는지 점검한 결과
- `implement`: 문서를 바탕으로 실제 구현을 진행한 결과

즉, Spec Kit은 "문서를 많이 만드는 도구"라기보다 "구현 전에 필요한 생각을 단계별 문서로 남기게 하는 작업 방식"에 가깝다.

## 한 기능이 실제로 어떻게 이어지는지 축약 예시

같은 가상 기능 하나가 단계별로 어떻게 바뀌는지 아주 짧게 이어서 보면 아래와 같다.

### 1. `spec.md`에서 시작

```md
## 기능 요구사항
- 시스템은 기획 문서에서 작업 후보를 추출해야 한다.
- 시스템은 작업 후보를 GitHub 이슈 초안 형태로 정리해야 한다.
```

### 2. `clarify`를 거치면 더 분명해짐

```md
## 명확화 기록
- Q: GitHub에 바로 이슈를 만들까? → A: 아니오, 초안만 만든다.
- Q: 누가 최종 승인하나? → A: PM 리뷰어

## 기능 요구사항
- 시스템은 GitHub에 바로 게시하지 않고 이슈 초안만 생성해야 한다.
- 시스템은 PM 리뷰어 승인 전에는 초안을 확정하면 안 된다.
```

### 3. `plan.md`에서는 설계 방향으로 바뀜

```md
## 기술 맥락
- GitHub와 직접 연동하되, 1차 버전은 초안 내보내기에만 집중한다.

## 원칙 점검
- 외부 연동 계약 문서가 필요하다.
- 원본 문서와 초안 사이의 추적 정보가 필요하다.
```

### 4. `tasks.md`에서는 실행할 일로 바뀜

여기서 `Phase`는 작업 단계, `사용자 시나리오`는 사용자 관점의 기능 묶음이라고 이해하면 된다.

```md
## Phase 1: 공통 기반
- [ ] 기획 문서 파싱 인터페이스를 만든다
- [ ] 이슈 초안 모델과 추적 링크 모델을 만든다

## Phase 2: 사용자 시나리오 - 이슈 초안 생성
- [ ] 작업 후보를 이슈 초안으로 변환하는 기능을 만든다
- [ ] 초안 생성 통합 테스트를 추가한다

## Phase 3: 사용자 시나리오 - 검토자 승인
- [ ] PM 리뷰어 승인 흐름을 추가한다
- [ ] 승인 전에는 내보낼 수 없도록 제한한다
```

### 5. `implement`에서는 실제 코드와 테스트가 나옴

```text
src/features/draft_issues/초안_생성.py
src/features/draft_issues/검토_승인.py
tests/integration/test_초안_생성.py
tests/integration/test_검토자_승인.py
```

이 연속 예시를 보면 Spec Kit의 핵심은 같다. 처음에는 "무엇을 만들까"를 적고, 그 다음 "빠진 질문은 무엇인가"를 메우고, 그 다음 "어떻게 설계할까"를 정하고, 마지막에 "무슨 작업을 할까"로 쪼개는 흐름이다.

## TCI 관점에서의 적용 포인트

TCI에서 Spec Kit을 볼 때는 아래처럼 이해하는 것이 가장 실용적이다.

- `constitution.md`: 이 프로젝트가 어떤 원칙으로 설계를 할지 정하는 기준
- `spec.md`: 기능 요구사항 정리본
- `clarify` 반영본: 설계 착수 가능 여부를 높인 명세
- `plan` 산출물 묶음: 기술 설계 입력
- `tasks.md`: 후속 backlog 또는 issue 전환용 작업 단위
- `analyze`: 설계 품질 점검
- `implement`: 필요할 때만 여는 실제 구현 단계

즉, TCI처럼 문서 중심으로 `기획 → 설계 입력`을 다루는 프로젝트에서는 `implement`보다 그 이전 단계 산출물의 품질이 더 중요하다.

## 참고 자료

- 로컬 가이드: [codex-cli 기준 spec-kit 사용 가이드.md](./codex-cli%20기준%20spec-kit%20사용%20가이드.md)
- 공식 저장소: https://github.com/github/spec-kit
- 공식 Quick Start: https://github.github.com/spec-kit/quickstart.html
- 공식 Methodology: https://github.com/github/spec-kit/blob/main/spec-driven.md
- 공식 `constitution-template`: https://github.com/github/spec-kit/blob/main/templates/constitution-template.md
- 공식 `spec-template`: https://github.com/github/spec-kit/blob/main/templates/spec-template.md
- 공식 `plan-template`: https://github.com/github/spec-kit/blob/main/templates/plan-template.md
- 공식 `tasks-template`: https://github.com/github/spec-kit/blob/main/templates/tasks-template.md
