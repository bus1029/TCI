# TCI에서 OpenSpec을 Codex CLI로 사용하는 가이드

- 작성 목적: `Fission-AI/OpenSpec`을 이 프로젝트에서 `Codex CLI` 기준으로 어떻게 도입하고 운영할지 정리
- 대상 프로젝트: `TCI`
- 작성 시점: 2026-04-14
- 기준 소스: OpenSpec 공식 사이트, 공식 README, `Getting Started`, `Commands`, `CLI`, `Supported Tools`, `Customization`, `CHANGELOG`

## 한줄 결론

`OpenSpec`은 이 프로젝트에서 충분히 써볼 만하다. 특히 기존 코드베이스 위에서 기능 변경 의도와 요구사항 델타를 남기는 용도에는 `spec-kit`보다 더 가볍고 빠르다. 현재 TCI의 Codex 환경은 OpenSpec Profile을 `Custom Selection`으로 업데이트해서 전체 OpenSpec skill 세트를 노출하는 상태이며, 문서를 볼 때도 `upstream /opsx:* 워크플로우 이름`, `OpenSpec CLI 실제 서브커맨드`, `현재 프로젝트에 실제로 보이는 Codex skill`을 구분해서 이해하면 가장 덜 헷갈린다.

중요한 전제도 있다. OpenAI 공식 Codex 문서 기준으로 `custom prompts`는 `2026-04-14` 시점에 deprecated 상태다. 완전히 제거된 것은 아니지만, 재사용 가능한 지시문은 `skills`를 쓰는 쪽이 현재 공식 권장 경로다.

이 프로젝트에서는 OpenSpec도 문서 보관 위치와 실제 설치 위치를 분리해서 이해해야 한다. 이 문서는 `mvp1-features/.../openspec/` 아래에 두지만, 실제 초기화는 레포 루트에서 해야 한다.

## 이 문서를 읽는 기준선

이 문서에서는 아래 세 가지를 명확히 구분한다.

### 1. upstream 워크플로우 이름

OpenSpec 공식 문서가 설명하는 `/opsx:*` 계열 개념 이름이다.

예:

- `/opsx:propose`
- `/opsx:explore`
- `/opsx:apply`
- `/opsx:archive`

이 이름은 "OpenSpec이 설명하는 워크플로우 단계"를 뜻한다. 지금 내 Codex에 그 이름의 skill이 실제로 보인다는 뜻은 아니다.

### 2. OpenSpec CLI 실제 명령

`openspec --help`에서 보이는 진짜 CLI 서브커맨드다.

예:

- `openspec init`
- `openspec update`
- `openspec list`
- `openspec new`
- `openspec archive`
- `openspec status`
- `openspec instructions`

즉, `/opsx:*`와 `openspec <subcommand>`는 같은 층이 아니다.

### 3. 현재 TCI Codex 환경에서 실제로 보이는 skill

`2026-04-15` 현재 이 프로젝트에서 확인된 skill은 아래 11개다.

- `$openspec-propose`
- `$openspec-explore`
- `$openspec-new-change`
- `$openspec-continue-change`
- `$openspec-ff-change`
- `$openspec-apply-change`
- `$openspec-verify-change`
- `$openspec-sync-specs`
- `$openspec-archive-change`
- `$openspec-bulk-archive-change`
- `$openspec-onboard`

즉, 현재 TCI Codex 환경은 OpenSpec의 기본 quick path뿐 아니라 확장 워크플로우에 해당하는 skill도 직접 호출 가능한 상태다.

## 먼저 알아둘 점

### 1. 이 문서 경로와 실제 설치 경로는 다르다

이 문서는 아래 경로에 보관한다.

```text
mvp1-features/requirements/design-to-feature-githubs/openspec/
```

하지만 실제 OpenSpec 초기화는 레포 루트에서 해야 한다.

```text
/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI
```

이유는 단순하다.

- `openspec/` 디렉터리는 실제 프로젝트 기준선이어야 함
- Codex용 skill도 프로젝트 루트 기준으로 생성하는 편이 가장 예측 가능함
- 하위 조사 폴더에 설치하면 실제 개발 워크플로우와 분리돼 버림

### 2. OpenSpec은 `spec-kit`과 생성 구조가 다르다

`spec-kit`은 `.specify/`, `specs/`, `.agents/skills/speckit-*` 흐름에 가깝다. 반면 OpenSpec은 기본적으로 아래 구조를 만든다.

```text
openspec/
  specs/
  changes/
  config.yaml

.codex/skills/
  openspec-*/
```

그리고 Codex용 prompt 파일은 프로젝트 안이 아니라 전역 Codex 홈에 생성된다.

```text
$CODEX_HOME/prompts/opsx-*.md
또는
~/.codex/prompts/opsx-*.md
```

즉, OpenSpec은 프로젝트 내부에 `openspec/`와 `.codex/skills`를 두고, 보조 명령 프롬프트는 전역 홈으로 빼는 방식이다. 다만 Codex 공식 문서상 이 `custom prompt` 경로는 deprecated이므로, 실사용 기준에서는 `skills`를 우선하고 `prompts`는 하위 호환 경로로 보는 편이 맞다.

### 3. TCI는 현재 `spec-kit` 거버넌스를 쓰고 있다

레포 루트 `README.md`에는 현재 아래 원칙이 이미 들어 있다.

- Spec Kit 기준 constitution을 사용
- 기획 문서를 설계 입력으로 먼저 구체화
- 명세와 계획을 고정한 뒤에만 구현 승인
- 초기 파일럿에서는 implement 자동 실행 금지

따라서 OpenSpec 도입은 당장 기존 원칙을 대체하는 작업이라기보다, `brownfield` 변경 관리와 lightweight change proposal 흐름을 검증하는 파일럿으로 보는 편이 맞다.

### 4. 1.0 이후에는 예전 `/openspec:*` 명령을 보면 안 된다

OpenSpec `1.0.0`부터는 예전 `legacy` 명령보다 `OPSX` 계열 명령이 기준이다. 따라서 오래된 블로그 글이나 예전 예시에서 아래 형태가 보이면 현재 기준으로는 구식일 가능성이 높다.

```text
/openspec:proposal
/openspec:apply
/openspec:archive
```

현재 공식 문서에서 설명하는 워크플로우 이름 기준은 아래다.

```text
/opsx:propose
/opsx:explore
/opsx:apply
/opsx:archive
```

확장 워크플로우 설명에서는 `new`, `continue`, `ff`, `verify`, `sync`, `bulk-archive`, `onboard`도 등장한다. 현재 TCI Codex 환경은 `Custom Selection`으로 업데이트되어 이 확장 워크플로우 skill까지 실제로 노출된 상태다.

## Codex CLI에서의 핵심 개념

### 1. OpenSpec의 기본 quick path는 `propose → apply → archive`다

공식 `core` 프로필 기준으로 OpenSpec의 기본 흐름은 아래다.

```text
/opsx:propose -> /opsx:apply -> /opsx:archive
```

이 흐름은 기능 변경을 빠르게 제안하고, 구현하고, 기준 spec으로 병합하는 데 맞춰져 있다. `spec-kit`처럼 `clarify`, `plan`, `tasks`를 별도 단계로 강하게 노출하기보다, `propose` 한 번에 `proposal`, `specs`, `design`, `tasks`를 한 번에 만든다는 점이 더 가볍다.

### 2. OpenSpec의 핵심 산출물은 change 폴더에 묶인다

OpenSpec은 각 변경 단위를 `openspec/changes/<change-name>/` 아래에 묶는다.

```text
openspec/changes/add-github-sync-rule/
  proposal.md
  design.md
  tasks.md
  specs/
    github-sync/
      spec.md
```

이때 중요한 구분은 다음 두 가지다.

- `openspec/specs/`: 현재 시스템 동작의 source of truth
- `openspec/changes/`: 제안 중인 변경 묶음

즉, main spec과 change delta가 분리된다.

### 3. Delta spec이 OpenSpec의 핵심이다

OpenSpec의 spec은 변경 전체를 다시 복사하는 방식보다 delta 방식이 핵심이다. 변경 spec에는 아래 섹션을 쓴다.

- `ADDED Requirements`
- `MODIFIED Requirements`
- `REMOVED Requirements`
- `RENAMED Requirements`

이 구조 덕분에 기존 기능 보강, 규칙 수정, 연동 동작 변경처럼 TCI가 자주 다룰 `brownfield` 작업을 문서화하기 쉽다.

### 4. Codex에서는 "지금 보이는 skill"과 "워크플로우 개념"을 구분해야 한다

공식 문서는 주로 `/opsx:*` 워크플로우 이름으로 설명한다. 하지만 Codex CLI 실사용 기준에서는 "현재 프로젝트에 실제로 생성된 skill"만 직접 호출할 수 있다.

| 구분 | 현재 TCI Codex 환경에서 확인된 항목 |
| --- | --- |
| 직접 호출 가능한 skill | `$openspec-propose`, `$openspec-explore`, `$openspec-new-change`, `$openspec-continue-change`, `$openspec-ff-change`, `$openspec-apply-change`, `$openspec-verify-change`, `$openspec-sync-specs`, `$openspec-archive-change`, `$openspec-bulk-archive-change`, `$openspec-onboard` |
| 공식 문서에서 보이는 워크플로우 이름 | `/opsx:propose`, `/opsx:explore`, `/opsx:apply`, `/opsx:archive` 등 |
| CLI 서브커맨드 | `openspec init`, `openspec update`, `openspec new`, `openspec archive`, `openspec status`, `openspec instructions` 등 |

즉 TCI의 현재 운영 기준은 아래처럼 이해하는 것이 가장 안전하다.

- OpenSpec 공식 문서를 읽을 때는 `/opsx:*`를 워크플로우 개념 이름으로 본다
- 실제 Codex 사용 시에는 지금 노출된 11개 skill을 직접 호출 가능한 것으로 본다
- 여전히 `/opsx:*` 워크플로우 이름과 `openspec <subcommand>` CLI는 다른 층으로 분리해서 이해한다

## 이 프로젝트에서 권장하는 설치 방식

### 전제 조건

- Node.js `20.19.0` 이상
- npm 전역 설치 가능
- Git 사용 가능
- Codex CLI 사용 가능

가장 단순한 공식 설치 명령은 아래다.

```bash
npm install -g @fission-ai/openspec@latest
```

설치 확인은 아래처럼 한다.

```bash
openspec --version
```

### TCI 레포에서 권장하는 초기화 명령

레포 루트에서 아래처럼 초기화하는 것을 권장한다.

```bash
cd /Users/seokhyunbae_1/Desktop/기획_스프린트/TCI
openspec init --tools codex --profile core
```

이 명령의 의미는 다음과 같다.

- `--tools codex`: Codex용 설정만 비대화형으로 생성
- `--profile core`: 기본 quick path 기준으로 시작

처음부터 여러 에이전트 도구를 같이 운영할 계획이 아니라면 `codex`만 선택하는 편이 관리가 쉽다.

### `--force`는 재초기화나 legacy 정리 때만 쓴다

공식 CLI에서 `--force`는 기존 legacy 파일 정리나 재초기화 시 자동 정리를 위한 옵션이다. 처음 도입 단계에서 무조건 붙일 필요는 없다.

예를 들어 아래 경우에만 고려하면 된다.

- 예전 OpenSpec 산출물이 이미 섞여 있음
- 초기화 중 legacy cleanup 확인 프롬프트를 없애고 싶음
- 실험 후 다시 깨끗하게 재생성하려 함

예시는 아래와 같다.

```bash
openspec init --tools codex --profile core --force
```

### `skills only`를 기본 운영 기준으로 둔다

OpenSpec 기본 delivery는 `both`다. 즉, skill과 command prompt를 둘 다 만든다. 그런데 Codex에서는 prompt 파일이 전역 `~/.codex/prompts/`에 생성된다.

OpenAI 공식 문서 기준으로 `custom prompts`는 deprecated이고, 재사용 가능한 지시문은 `skills` 사용이 권장된다. 따라서 TCI 운영 기준은 아래처럼 잡는 편이 맞다.

1. 기본 도입은 `skills` 중심
2. deprecated된 전역 `prompts` 경로는 기본값으로 채택하지 않음
3. 실제 사용은 `openspec-*` skill 기준

delivery 변경은 아래처럼 한다.

```bash
openspec config profile
```

여기서 delivery를 `skills only`로 바꾸고, 이후 현재 프로젝트에 반영하려면 아래를 실행한다.

```bash
openspec update
```

## 초기화 후 기대되는 구조

대략 아래 구조를 기대하면 된다.

```text
openspec/
  specs/
  changes/
  config.yaml

.codex/
  skills/
    openspec-propose/
    openspec-explore/
    openspec-apply-change/
    openspec-archive-change/

~/.codex/prompts/
  opsx-propose.md
  opsx-explore.md
  opsx-apply.md
  opsx-archive.md
```

주의할 점은 다음과 같다.

- `.codex/skills`는 프로젝트 안에 생김
- `opsx-*.md`는 전역 홈에 생길 수 있지만 Codex 공식 문서상 deprecated 경로임
- `openspec/` 산출물은 레포에 커밋 가능한 문서 자산임

## Codex CLI에서 실제로 쓰는 방법

### 1단계: Codex를 다시 시작하고 skill 인식 확인

초기화 또는 `openspec update` 뒤에는 Codex 세션을 다시 여는 편이 안전하다.

확인 방식은 아래처럼 단순하다.

- Codex 프롬프트에 `$` 입력
- `openspec-propose`, `openspec-explore`, `openspec-apply-change`, `openspec-archive-change`뿐 아니라 `openspec-verify-change`, `openspec-sync-specs`, `openspec-continue-change` 등 전체 skill이 보이는지 확인

보이지 않으면 아래를 먼저 의심하면 된다.

- `openspec init --tools codex`가 실제 레포 루트에서 실행됐는지
- `.codex/skills/openspec-*`가 생성됐는지
- Codex 세션이 초기화 이전 상태를 계속 보고 있는지
- `openspec update`를 다시 해야 하는 상태인지

### 2단계: 가장 먼저 `explore` 또는 `propose`부터 쓴다

OpenSpec 공식 quick path 기준 첫 진입점은 `propose`다. 다만 요구사항이 흐릿하면 먼저 `explore`로 들어가는 편이 좋다.

예시는 아래처럼 잡으면 된다.

```text
$openspec-explore
현재 GitHub 연동 흐름에서 webhook 수신 이후 상태 반영 규칙을 어떻게 정리할지 조사해줘
```

요구사항이 이미 어느 정도 닫혀 있다면 바로 아래처럼 간다.

```text
$openspec-propose
GitHub 이슈 상태와 내부 티켓 상태 동기화 규칙을 명세와 작업 단위까지 정리해줘
```

이 단계가 끝나면 보통 아래 산출물이 함께 생긴다.

- `proposal.md`
- delta spec
- `design.md`
- `tasks.md`

### 3단계: 구현 전에는 문서를 먼저 검토한다

OpenSpec은 가벼운 툴이지만, TCI 운영 기준에서는 구현 자동화를 바로 허용하지 않는 편이 맞다. 따라서 `apply` 전에 아래를 먼저 본다.

- `proposal.md`의 문제 정의와 범위
- delta spec의 요구사항 변화
- `design.md`의 기술 접근
- `tasks.md`의 작업 분해 품질

실무적으로는 이 시점에서 리뷰가 핵심이다.

### 4단계: 구현이 필요할 때만 `apply`를 연다

예시는 아래처럼 간다.

```text
$openspec-apply-change
add-github-sync-rule 변경의 미완료 task만 구현해줘
```

공식 문서 기준으로 `apply`는 `tasks.md`의 체크박스를 읽고 코드 작업을 진행한다. 따라서 TCI 초기 파일럿에서는 아래 원칙을 권장한다.

- 초기에는 `proposal/specs/design/tasks` 생성 품질 검증이 우선
- 구현 자동화는 작은 변경부터 제한적으로 허용
- 큰 변경은 사람이 문서 검토 후 실행

### 5단계: 구현 후에는 `verify`와 `archive`로 닫는다

현재 TCI Codex 환경에서는 `verify-change`와 `archive-change`를 모두 직접 사용할 수 있다.

구현 검증은 아래처럼 진행할 수 있다.

```text
$openspec-verify-change
add-github-sync-rule 구현이 spec과 design에 맞는지 검증해줘
```

최종 반영은 아래처럼 닫는다.

```text
$openspec-archive-change
add-github-sync-rule 변경을 archive해줘
```

`archive`는 delta spec을 main spec으로 합치고, change 폴더를 `openspec/changes/archive/YYYY-MM-DD-<name>/` 아래로 이동시킨다.

현재 환경에서는 아래 전체를 직접 호출할 수 있다.

- `propose`
- `explore`
- `new-change`
- `continue-change`
- `ff-change`
- `apply-change`
- `verify-change`
- `sync-specs`
- `archive-change`
- `bulk-archive-change`
- `onboard`

## 확장 워크플로우와 현재 환경

기본 `core` 프로필은 아래 네 개만 포함한다.

- `propose`
- `explore`
- `apply`
- `archive`

지금 TCI 환경은 OpenSpec Profile을 `Custom Selection`으로 업데이트해서, 확장 워크플로우 skill까지 모두 보이는 상태다.

```bash
openspec config profile
openspec update
```

현재 직접 사용할 수 있는 확장 skill은 아래다.

- `new`: change scaffold만 먼저 생성
- `continue`: 다음 artifact를 하나씩 생성
- `ff`: planning artifact를 한 번에 생성
- `verify`: 구현이 명세와 맞는지 확인
- `sync`: delta spec만 먼저 main spec으로 반영
- `bulk-archive`: 여러 change를 한꺼번에 archive
- `onboard`: 튜토리얼형 첫 실행

TCI에서는 아래 기준을 권장한다.

- 기능 기획이 아직 흐리면 `explore`
- 변경은 만들되 문서를 하나씩 검토하고 싶으면 `new + continue`
- 기획이 비교적 닫혀 있으면 `propose` 또는 `new + ff`
- 구현 전후 정합성을 보려면 `verify`
- delta spec을 먼저 기준선에 맞춰 보려면 `sync`

## TCI에서 권장하는 운영 방식

### 1. OpenSpec은 brownfield 변경 관리 용도로 먼저 파일럿한다

OpenSpec은 새 기능 백지 설계보다 기존 기능 변경, 규칙 보강, 연동 흐름 수정에 더 잘 맞는다. 따라서 TCI에서는 아래 유형부터 붙여보는 편이 좋다.

- GitHub 연동 규칙 변경
- 티켓 상태 동기화 규칙 변경
- 문서-코드 추적 정책 보강
- 기존 워크플로우 보완

### 2. 기본 schema를 그대로 쓰지 말고 TCI용 schema를 검토한다

OpenSpec의 강점은 `openspec/schemas/` 아래에서 custom schema를 만들 수 있다는 점이다. TCI에 맞추려면 나중에 아래 artifact를 추가하는 편이 유리하다.

- `review.md`
- `readiness-check.md`
- `research.md`
- `data-model.md`

시작은 공식 schema를 fork하는 방식이 가장 쉽다.

```bash
openspec schema fork spec-driven tci-design-input
```

이후 `openspec/config.yaml`에서 기본 schema를 지정하면 된다.

```yaml
schema: tci-design-input
```

### 3. `config.yaml`에 프로젝트 컨텍스트를 넣어야 품질이 오른다

OpenSpec은 `openspec/config.yaml`에 프로젝트 문맥과 artifact별 규칙을 주입할 수 있다. 이건 TCI처럼 문서 품질 편차를 줄여야 하는 프로젝트에서 중요하다.

예를 들면 아래 같은 규칙을 넣을 수 있다.

```yaml
schema: spec-driven

context: |
  Project: TCI
  Goal: 기획 문서를 설계 입력으로 구체화한 뒤 구현을 승인한다
  Current governance: README의 Spec Kit 원칙을 기본 참조로 유지한다

rules:
  proposal:
    - 범위 제외 항목을 반드시 적는다
    - 기존 워크플로우와 충돌 가능성을 적는다
  specs:
    - Given/When/Then 시나리오를 유지한다
    - 변경 전후 차이가 드러나게 쓴다
  design:
    - 시스템 경계와 외부 연동 포인트를 명시한다
  tasks:
    - 구현 전에 검토 가능한 단위로 쪼갠다
```

### 4. `openspec update`를 운영 루틴에 포함한다

OpenSpec은 버전 업그레이드 뒤 instruction 파일을 다시 생성하는 `openspec update`를 전제로 한다. 따라서 운영 루틴은 아래처럼 잡는 편이 좋다.

```bash
npm install -g @fission-ai/openspec@latest
openspec update
```

문서 기준으로도 프로필이나 delivery를 바꾼 뒤에는 `openspec update`가 사실상 필수다.

## TCI 관점에서의 장단점 요약

### 장점

- 기존 시스템 변경을 delta spec으로 다루기 쉬움
- `proposal`, `design`, `tasks`, spec delta가 한 change 폴더에 모임
- `spec-kit`보다 가볍게 시작 가능
- Codex를 공식 지원함
- custom schema로 TCI 전용 artifact 체계를 만들기 쉬움

### 단점

- 기본형만 쓰면 `clarify`, `research`, `data-model`, `contracts` 같은 설계 강제력이 약함
- OpenSpec 기본 delivery가 `both`라서, 설정을 손보지 않으면 deprecated된 `~/.codex/prompts` 경로까지 함께 생성될 수 있음
- 현재 TCI README는 Spec Kit 거버넌스를 전제로 하므로 즉시 대체는 어색함
- 문서가 빠르게 변하는 제품이라 운영 기준을 내부적으로 한 번 더 고정해야 함

## 이 프로젝트에서의 권장 결론

현재 TCI에서 OpenSpec을 쓰려면 아래처럼 이해하면 된다.

- `spec-kit` 대체재라기보다 `brownfield 변경 관리용 lightweight 레이어`
- 레포 루트에서 `openspec init --tools codex --profile core`로 시작
- Codex에서는 현재 보이는 11개 skill 호출을 실사용 기준으로 삼음
- deprecated된 custom prompt 경로는 사용 가능하더라도 기본 운영 경로로 채택하지 않음
- 구현 자동화보다 `proposal/specs/design/tasks` 품질 검토를 먼저 파일럿
- 파일럿이 맞으면 이후 `custom schema`로 TCI 전용 artifact를 추가

즉, OpenSpec은 TCI에서 "기획을 설계로 옮기는 가벼운 change proposal 엔진"으로는 꽤 유력하다. 다만 현재 거버넌스를 바로 갈아엎는 도구라기보다, `spec-kit`보다 가볍고 변경 중심인 대안을 실험하는 용도로 보는 편이 맞다.

## 참고 링크

- OpenAI Codex Custom Prompts: https://developers.openai.com/codex/custom-prompts
- OpenAI Codex Skills: https://developers.openai.com/codex/skills
- 공식 사이트: https://openspec.dev/
- 저장소: https://github.com/Fission-AI/OpenSpec
- README: https://github.com/Fission-AI/OpenSpec/blob/main/README.md
- Getting Started: https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md
- Commands: https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md
- CLI Reference: https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md
- Supported Tools: https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md
- Customization: https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md
- CHANGELOG: https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md
