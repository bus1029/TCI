# TCI에서 spec-kit을 Codex CLI로 사용하는 가이드

- 작성 목적: `github/spec-kit`을 이 프로젝트에서 `Codex CLI` 기준으로 어떻게 도입하고 운영할지 정리
- 대상 프로젝트: `TCI`
- 작성 시점: 2026-04-09
- 기준 소스: `github/spec-kit` 공식 README, Quick Start, Installation, Presets 문서와 OpenAI Codex 공식 skills 문서

## 한줄 결론

`spec-kit`은 이 프로젝트에서 충분히 써볼 만하다. 다만 `Codex CLI`에서는 upstream 문서의 `/speckit.*` 예시를 그대로 따라가기보다 `--ai codex --ai-skills`로 설치하고, 실제 호출은 `$speckit-*` skill 방식으로 쓰는 것이 기준이다.

이 프로젝트에서는 `spec-kit`을 `mvp1-features/.../spec-kit/` 아래에 설치하는 것이 아니라 레포 루트에 붙여야 한다. 이유는 Codex가 `.agents/skills`를 현재 작업 디렉터리에서 레포 루트까지 위로만 스캔하기 때문이다.

## 먼저 알아둘 점

### 1. 이 문서 경로와 실제 설치 경로는 다르다

이 문서는 아래 경로에 보관한다.

```text
mvp1-features/requirements/design-to-feature-githubs/spec-kit/
```

하지만 실제 `spec-kit` 초기화는 레포 루트에서 해야 한다.

```text
/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI
```

그 이유는 다음과 같다.

- Codex는 `.agents/skills`를 현재 작업 디렉터리에서 부모 방향으로만 읽음
- 따라서 하위 폴더에만 skill을 설치하면 레포 루트에서 띄운 Codex 세션에서는 보이지 않을 수 있음
- 이 프로젝트처럼 레포 전체 워크플로우에 붙일 도구는 루트 기준으로 두는 편이 맞음

### 2. 이 레포는 이미 `.agents/skills`를 쓰고 있다

현재 TCI 레포 루트에는 이미 `.agents/skills`가 있고, 여러 gstack skill이 들어 있다. `spec-kit`을 Codex 방식으로 초기화하면 여기에 `speckit-*` 계열 skill이 추가되는 형태가 된다.

즉, `spec-kit`은 별도 시스템이 아니라 기존 Codex skill 생태계에 합류하는 방식으로 이해하면 된다.

### 3. 현재는 `.specify/`가 없다

지금 레포에는 아직 `.specify/`가 없다. `specify init`을 실행하면 보통 아래 두 축이 새로 생긴다.

- `.specify/`
- `specs/`

이 둘이 `spec-kit`의 실질적인 작업 기준선이 된다.

## Codex CLI에서의 핵심 개념

### 1. Codex에서는 slash command보다 skill invocation이 기준이다

`spec-kit` 공식 문서는 대부분 다음 형태로 설명한다.

```text
/speckit.constitution
/speckit.specify
/speckit.clarify
/speckit.plan
/speckit.tasks
/speckit.implement
```

하지만 `Codex CLI`에서는 최신 권장 방식이 skill 기반이다. 따라서 Codex에서는 다음처럼 생각하면 된다.

| upstream 개념 | Codex CLI에서의 사용 방식 |
| --- | --- |
| `/speckit.constitution` | `$speckit-constitution` |
| `/speckit.specify` | `$speckit-specify` |
| `/speckit.clarify` | `$speckit-clarify` |
| `/speckit.plan` | `$speckit-plan` |
| `/speckit.tasks` | `$speckit-tasks` |
| `/speckit.implement` | `$speckit-implement` |

실무적으로는 다음 규칙으로 보면 된다.

- upstream 문서에서 `/speckit.xxx`를 보면 Codex에서는 먼저 `$speckit-xxx`로 번역
- skill 이름만 부르는 것이 아니라 같은 프롬프트에 필요한 설명도 함께 적기
- Codex에서 `$` 입력으로 skill selector를 열어 `speckit-*`가 보이는지 확인

### 2. Codex는 skill을 위쪽 디렉터리에서 발견한다

OpenAI 공식 skills 문서 기준으로 Codex는 레포 내부에서 현재 디렉터리부터 레포 루트까지의 `.agents/skills`를 읽는다.

이 말은 곧 다음을 뜻한다.

- 레포 루트에 설치하면 하위 폴더 어디서 Codex를 띄워도 비교적 안정적으로 사용 가능
- 하위 폴더에만 설치하면 그 하위 폴더에서 시작한 세션에서만 보일 수 있음

TCI에서는 레포 루트 설치가 정답에 가깝다.

## 이 프로젝트에서 권장하는 설치 방식

### 전제 조건

- `uv` 설치
- Python 3.11+
- Git 사용 가능
- Codex CLI 사용 가능

설치가 끝난 뒤에는 아래 확인을 권장한다.

```bash
specify check
```

아직 `specify`를 설치하지 않았다면 두 가지 방식이 있다.

### 1. 지속 설치 방식

가장 무난한 방식이다.

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
```

이후에는 아래처럼 직접 쓴다.

```bash
specify check
```

### 2. 일회성 실행 방식

로컬 설치를 최소화하고 싶다면 `uvx`로 바로 실행해도 된다.

```bash
uvx --from git+https://github.com/github/spec-kit.git@vX.Y.Z specify check
```

`vX.Y.Z`는 실행 시점의 최신 안정 태그로 치환하면 된다. 공식 문서도 특정 릴리스 태그 고정을 권장한다.

## TCI 레포에서 실제 초기화 명령

이 레포는 이미 비어 있지 않으므로 루트에서 `--here`와 상황에 따라 `--force`가 필요할 가능성이 높다.

권장 명령은 아래다.

```bash
specify init --here --force --ai codex --ai-skills --script sh
```

설명은 다음과 같다.

- `--here`: 현재 레포 루트에 붙임
- `--force`: 비어 있지 않은 디렉터리에도 초기화
- `--ai codex`: Codex CLI용 설정 선택
- `--ai-skills`: Codex용 prompt 대신 skill 방식으로 설치
- `--script sh`: macOS 환경에 맞춰 POSIX shell 스크립트 선택

Codex 탐지가 환경상 실패하면 아래 옵션을 추가할 수 있다.

```bash
specify init --here --force --ai codex --ai-skills --script sh --ignore-agent-tools
```

## 초기화 후 기대되는 구조

구체적인 템플릿 버전에 따라 조금 달라질 수 있지만, 큰 틀은 다음과 같다.

```text
.agents/skills/
  speckit-constitution/
  speckit-specify/
  speckit-clarify/
  speckit-plan/
  speckit-tasks/
  speckit-implement/

.specify/
  memory/
    constitution.md
  scripts/
    ...
  templates/
    ...

specs/
  001-some-feature/
    spec.md
    plan.md
    tasks.md
    research.md
    data-model.md
    quickstart.md
    contracts/
```

핵심은 아래 두 가지다.

- Codex가 읽는 진입점은 `.agents/skills`
- 기능 산출물이 쌓이는 곳은 `.specify/`와 `specs/`

## Codex CLI에서 실제로 쓰는 방법

### 1단계: Codex를 다시 시작하고 skill 인식 확인

초기화 뒤에는 Codex 세션을 새로 여는 편이 안전하다.

확인 방식은 단순하다.

- Codex 프롬프트에서 `$` 입력
- `speckit-constitution`, `speckit-specify` 등이 보이는지 확인

보이지 않으면 아래를 먼저 의심한다.

- 레포 루트가 아닌 하위 경로에 설치했는지
- `.agents/skills`가 예상 위치가 맞는지
- 기존 Codex 세션이 초기화 전 상태를 캐시하고 있는지

### 2단계: constitution 작성

첫 번째 실사용 단계는 constitution이다.

Codex 프롬프트 예시는 아래처럼 잡으면 된다.

```text
$speckit-constitution
TCI 프로젝트의 constitution 초안을 작성해줘.
다음 원칙을 반드시 반영해줘.
- 기획을 설계 입력으로 구체화하는 문서 중심 개발
- 구현보다 명세와 계획을 먼저 고정
- 변경 이력 추적 가능해야 함
- 외부 시스템 연동은 계약과 데이터 모델을 명시
- 초기 파일럿에서는 implement 단계 자동 실행 금지
```

산출물은 보통 `.specify/memory/constitution.md`에 쌓인다.

### 3단계: feature branch 기준으로 specify 시작

Spec Kit quickstart는 active feature를 현재 Git branch 기준으로 감지한다고 설명한다. 따라서 `main`에서 여러 기능을 섞기보다 기능별 branch를 먼저 잡는 편이 안전하다.

예시:

```bash
git checkout -b 001-github-design-to-feature
```

그 다음 Codex에서:

```text
$speckit-specify
TCI에서 GitHub 저장소의 design-to-feature 흐름을 지원하는 기능을 명세화해줘.
목표는 다음과 같아.
- 기획 문서를 기능 요구사항과 수용 기준으로 정리
- GitHub 이슈 또는 작업 단위로 이어질 수 있어야 함
- 코드 저장소, 티켓 시스템, 문서 시스템 간 추적성을 고려
- 이번 범위는 구현보다 설계 입력 문서 생성까지
```

이 단계에서는 기술 스택보다 문제 정의와 사용자 가치, 범위를 분명히 적는 것이 중요하다.

### 4단계: clarify로 설계 착수 가능 여부를 닫기

TCI에는 이 단계가 특히 중요하다. 현재 레포의 목적도 `기획을 설계로 구체화`하는 쪽이기 때문이다.

예시:

```text
$speckit-clarify
다음 항목이 비어 있으면 질문으로 드러내줘.
- 설계 착수 가능 여부
- 외부 시스템 경계
- 수용 기준
- 제외 범위
- 데이터 소스와 권한 가정
```

이 단계의 실무 포인트는 다음과 같다.

- 질문이 나오면 바로 구현으로 가지 말고 명세를 닫는 데 사용
- 질문 응답이 끝난 뒤 `spec.md`를 다시 읽고 남은 모호성이 없는지 확인
- TCI에서는 이 시점이 `설계 착수 판단 기준`과 가장 강하게 연결됨

### 5단계: plan으로 기술 설계 입력 만들기

`plan`은 TCI에서 가장 직접적인 가치가 있는 단계다.

예시:

```text
$speckit-plan
기술 계획은 다음 제약을 반영해줘.
- 이 프로젝트는 문서와 분석 산출물이 중요한 레포다
- 구현보다 설계 입력 문서 품질을 우선한다
- 외부 연동은 contracts와 data-model을 분리해서 남긴다
- 초기 파일럿은 GitHub 연동 범위만 다룬다
- 검증 포인트와 비범위 항목을 명확히 적어줘
```

이 단계에서 기대하는 핵심 산출물은 보통 아래다.

- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/`
- `quickstart.md`

### 6단계: tasks 생성

예시:

```text
$speckit-tasks
구현 자동화용 세부 작업보다는 설계 검토와 후속 backlog 전환에 적합한 작업 단위로 나눠줘.
문서 검토, 계약 검토, 데이터 모델 검토, 추적성 검토를 포함해줘.
```

TCI에서는 초도 도입 시 `tasks`까지만 쓰는 것을 권장한다.

즉, 초기 운영 원칙은 아래다.

- `constitution`
- `specify`
- `clarify`
- `plan`
- `tasks`

여기서 멈춘다.

### 7단계: implement는 나중에 연다

upstream 워크플로우에는 `implement`가 있지만, 이 레포의 현재 목적에는 바로 연결하지 않는 편이 맞다.

초기 파일럿에서는 다음 이유로 `implement`를 닫아두는 것을 권장한다.

- 지금 목적은 구현 자동화보다 설계 입력 문서화
- 문서 품질과 경계 정의가 먼저 검증되어야 함
- 기존 `.agents/skills` 체계와도 역할 충돌을 줄일 수 있음

## 이 프로젝트에 맞는 운영 원칙

### 1. spec-kit 산출물은 루트에 두고, 연구 문서는 현재 폴더에 둔다

정리하면 역할 분담은 다음이 좋다.

| 위치 | 역할 |
| --- | --- |
| `.specify/`, `specs/` | spec-kit의 원본 산출물 |
| `mvp1-features/requirements/design-to-feature-githubs/spec-kit/` | 도입 가이드, 평가 문서, 회고, preset 설계 메모 |

즉, 지금 이 폴더는 설명서와 리서치용이다. spec-kit의 런타임 산출물 저장소로 쓰는 곳이 아니다.

### 2. spec-kit 출력물을 기존 TCI 문서 체계와 매핑한다

권장 매핑은 아래다.

| TCI 목적 | spec-kit 대응 |
| --- | --- |
| 기능 요구사항 정리 | `spec.md` |
| 설계 착수 가능 여부 판단 | `clarify` 결과 + `spec.md` 수정본 |
| 기술 설계 입력 | `plan.md`, `research.md`, `contracts/`, `data-model.md` |
| 후속 실행 단위 | `tasks.md` |

### 3. 산출물은 Git에 포함하는 편이 맞다

이 레포는 아직 루트 `.gitignore`가 없고, `spec-kit`의 문서 산출물은 원칙적으로 소스 오브 트루스로 다루는 편이 자연스럽다.

따라서 초기 판단은 다음이 적절하다.

- `.specify/` 추적
- `specs/` 추적
- 임시 캐시나 개인 실험 파일만 별도 정리

### 4. 처음부터 preset보다 override가 가볍다

TCI 맞춤화는 두 단계로 보는 것이 현실적이다.

### 1차

프로젝트 로컬 override만 사용

후보 경로:

```text
.specify/templates/overrides/
```

우선순위가 높은 후보 파일:

- `constitution-template.md`
- `spec-template.md`
- `plan-template.md`
- `tasks-template.md`

### 2차

운영 방식이 굳으면 preset으로 승격

유용한 명령:

```bash
specify preset search
specify preset add --dev ./my-preset
specify preset list
specify preset resolve spec-template
```

presets 문서 기준으로 템플릿 탐색 우선순위는 대략 아래 순서다.

1. `.specify/templates/overrides/`
2. `.specify/presets/...`
3. `.specify/extensions/...`
4. `.specify/templates/`

즉, 초기에 TCI 전용 문구만 바꿀 때는 override가 가장 단순하다.

## 추천 파일럿 시나리오

처음부터 전면 도입하기보다 아래 중 하나에 붙여보는 것이 좋다.

- 코드 저장소 연동
- 티켓 시스템 연동
- 문서와 코드 간 불일치 분석
- 문서-이슈-코드 추적성 관리

권장 순서는 아래다.

1. 레포 루트에서 `specify init --here --force --ai codex --ai-skills --script sh`
2. Codex 재시작 후 `speckit-*` skill 인식 확인
3. TCI constitution 작성
4. 파일럿용 feature branch 생성
5. `$speckit-specify`
6. `$speckit-clarify`
7. `$speckit-plan`
8. `$speckit-tasks`
9. 산출물을 기존 TCI 문서 체계와 비교 검토
10. 필요한 템플릿 수정 포인트를 `.specify/templates/overrides/`로 흡수

## 자주 걸리는 문제

### 1. Codex에서 `speckit-*`가 안 보인다

우선 확인할 것:

- 레포 루트에서 초기화했는지
- `.agents/skills` 아래에 `speckit-*`가 실제로 생겼는지
- Codex를 재시작했는지
- `--ai codex --ai-skills`로 초기화했는지

### 2. upstream 문서에는 `/speckit.plan`인데 Codex에서는 다르다

정상이다. Codex는 skill 기반 사용을 권장한다. 이 경우 `/speckit.plan` 예시를 `$speckit-plan`으로 번역해서 사용하면 된다.

### 3. 기존 `.agents/skills`와 충돌하지 않을까

이 레포처럼 이미 다른 skill이 있어도 이름이 겹치지 않으면 공존 가능성이 높다. 다만 신규 초기화가 `.agents/` 아래를 수정하므로 별도 branch에서 시작하는 편이 안전하다.

### 4. implement까지 바로 가야 하나

지금 TCI의 목적에는 아니다. 초기 파일럿은 문서 품질 검증에 집중하고 `tasks`까지만 쓰는 편이 더 낫다.

## 최종 권장안

이 프로젝트에서 `spec-kit`을 써보려면 아래처럼 접근하는 것이 가장 현실적이다.

- 설치 위치는 레포 루트
- Codex 호출 방식은 `$speckit-*`
- 초기 범위는 `constitution → specify → clarify → plan → tasks`
- 산출물 저장은 `.specify/`와 `specs/`
- TCI 맞춤화는 처음엔 `overrides`, 나중엔 `preset`
- 실제 파일럿은 GitHub 연동 또는 추적성 관련 기능 하나로 제한

이렇게 가면 `spec-kit`을 이 레포의 기존 문서 중심 흐름에 무리 없이 붙여볼 수 있다.

## 참고 문서

- Spec Kit README: https://github.com/github/spec-kit
- Spec Kit Quick Start: https://github.github.com/spec-kit/quickstart.html
- Spec Kit Installation Guide: https://github.github.com/spec-kit/installation.html
- Spec Kit Presets: https://github.com/github/spec-kit/tree/main/presets
- OpenAI Codex Skills: https://developers.openai.com/codex/skills
