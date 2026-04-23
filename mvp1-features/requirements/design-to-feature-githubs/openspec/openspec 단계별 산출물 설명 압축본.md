# OpenSpec 단계별 산출물 설명 압축본

- 작성일: 2026-04-15
- 대상: `Fission-AI/OpenSpec`을 `Codex CLI` 기준으로 사용할 때 생성되거나 갱신되는 단계별 산출물
- 목적: 처음 보는 사람도 OpenSpec의 각 단계에서 어떤 파일이 생기고, 그 파일이 왜 필요한지 빠르게 이해할 수 있게 정리

## 한줄 요약

OpenSpec은 기능 변경을 바로 구현으로 넘기지 않고, `변경 제안 -> 요구사항 델타 -> 기술 설계 -> 작업 분해 -> 구현 -> 검증 -> 기준 spec 반영` 순서로 문서를 쌓아 가는 방식이다. 핵심은 `현재 기준선(specs)`과 `제안 중인 변경(changes)`을 분리해서 관리하는 데 있다.

현재 TCI Codex 환경은 OpenSpec Profile을 `Custom Selection`으로 업데이트해서, 기본 quick path와 확장 워크플로우까지 포함한 전체 OpenSpec skill 세트를 직접 호출할 수 있는 상태다.

## 먼저 알아둘 점

### OpenSpec에서 산출물이란 무엇인가

이 문서에서 말하는 `산출물`은 각 단계가 끝났을 때 실제로 파일 시스템에 남는 결과물을 뜻한다. 대표적으로 아래가 있다.

- `openspec/config.yaml`
- `openspec/specs/<capability>/spec.md`
- `openspec/changes/<change-name>/proposal.md`
- `openspec/changes/<change-name>/design.md`
- `openspec/changes/<change-name>/tasks.md`
- `openspec/changes/<change-name>/specs/<capability>/spec.md`
- archive 후 갱신되는 기준선 spec

즉, 대화 내용이 아니라 다음 단계와 다음 사람에게 넘길 수 있는 실제 기준 문서라고 보면 된다.

### 현재 TCI Codex 환경에서 바로 호출 가능한 단계

현재 이 프로젝트에서 Codex skill로 직접 보이는 것은 아래 11단계다.

- `onboard`
- `explore`
- `propose`
- `new-change`
- `continue-change`
- `ff-change`
- `apply-change`
- `verify-change`
- `sync-specs`
- `archive-change`
- `bulk-archive-change`

### OpenSpec의 핵심 구조는 두 층이다

OpenSpec을 이해할 때 가장 중요한 구조는 아래 둘이다.

- `openspec/specs/`
  현재 시스템이 실제로 따라야 하는 기준선 규격
- `openspec/changes/`
  아직 제안 중이거나 구현 중인 변경 묶음

이 둘이 분리되어 있기 때문에, 기존 동작과 새 변경안을 뒤섞지 않고 관리할 수 있다.

### OpenSpec은 delta spec 중심이다

Spec Kit이 기능별 완성형 `spec.md`를 먼저 잡는 흐름에 더 가깝다면, OpenSpec은 기존 시스템 위에서 `무엇이 추가되거나 수정되는지`를 delta로 기록하는 데 강하다.

대표 섹션:

- `ADDED Requirements`
- `MODIFIED Requirements`
- `REMOVED Requirements`
- `RENAMED Requirements`

즉 OpenSpec의 핵심 가치는 "새 기능 문서 생성" 자체보다 "기존 기준선 대비 어떤 요구사항이 바뀌는지"를 추적 가능하게 만드는 데 있다.

## 전체 흐름 한눈에 보기

처음 보는 사람은 명령보다 산출물 흐름으로 이해하는 편이 쉽다.

| 순서 | 단계 | 현재 TCI Codex에서 직접 호출 가능 여부 | 입력 | 대표 산출물 | 다음 단계로 넘기는 것 |
| --- | --- | --- | --- | --- | --- |
| 1 | `init` | 아니오, CLI 단계 | 빈 프로젝트 또는 기존 레포 | `openspec/`, `.codex/skills/openspec-*` | OpenSpec 작업장 |
| 2 | `onboard` | 예 | 기존 프로젝트 맥락 | 온보딩 메모, 기본 설정 보강 | 프로젝트 이해 컨텍스트 |
| 3 | `explore` | 예 | 문제 인식, 아이디어, 기존 문서 | 보통 새 파일 없음 또는 조사 메모 | proposal로 넘길 생각 정리 |
| 4 | `propose` | 예 | 변경 설명 또는 change name | `proposal.md`, `design.md`, `tasks.md`, `changes/<name>/specs/**` | 구현 가능한 변경 패키지 |
| 5 | `new` | 예, `new-change`로 노출 | change name | `changes/<name>/` 골격 | 수동 작성 시작점 |
| 6 | `continue` / `ff` | 예 | 기존 change | 기존 change 갱신 | 이어서 설계 또는 구현 |
| 7 | `apply` | 예, `apply-change`로 노출 | proposal/design/tasks/specs | 코드, 테스트, 문서 변경 | 실제 구현 결과 |
| 8 | `verify` | 예, `verify-change`로 노출 | 구현 결과와 change 문서 | 검증 결과, 실패/누락 확인 | archive 전 품질 판단 |
| 9 | `sync` | 예, `sync-specs`로 노출 | 기준선과 change 문서 | 동기화된 spec 구조 | archive 준비 |
| 10 | `archive` | 예, `archive-change`로 노출 | 완료된 change | archive 기록, 갱신된 `openspec/specs/` | 새 기준선 |
| 11 | `bulk-archive` | 예, `bulk-archive-change`로 노출 | 다수 완료 change | 일괄 archive 결과 | 정리된 기준선 |

## 용어 빠르게 보기

- `change`: 하나의 변경 단위
- `capability`: spec을 나누는 기능 단위
- `baseline spec`: 현재 기준선 규격
- `delta spec`: 기존 기준선에 대한 변경점
- `proposal`: 왜 이 변경이 필요한지 정리한 문서
- `design`: 어떻게 구현할지 정리한 기술 설계 문서
- `tasks`: 구현 가능한 체크리스트
- `archive`: 변경안을 기준선에 반영하고 변경 폴더를 정리하는 단계

## 1. 초기화: `openspec init`

### 주요 산출물

- `openspec/`
- `openspec/config.yaml`
- `openspec/specs/`
- `openspec/changes/`
- `.codex/skills/openspec-*`

### 이 산출물의 의미

이 단계는 기능 문서를 만드는 단계가 아니라 OpenSpec 작업장을 세팅하는 단계다.

- `openspec/config.yaml`: 어떤 schema를 쓸지, AI가 artifact를 만들 때 어떤 규칙을 참고할지 정하는 기본 설정
- `openspec/specs/`: 현재 기준선 spec이 쌓이는 위치
- `openspec/changes/`: 변경안이 임시로 쌓이는 위치
- `.codex/skills/openspec-*`: Codex CLI에서 각 단계 명령을 skill로 호출하기 위한 진입점

### 예시

```text
openspec/
  config.yaml
  specs/
  changes/

.codex/skills/
  openspec-propose/
  openspec-explore/
  openspec-new-change/
  openspec-continue-change/
  openspec-ff-change/
  openspec-apply-change/
  openspec-verify-change/
  openspec-sync-specs/
  openspec-archive-change/
  openspec-bulk-archive-change/
  openspec-onboard/
```

### 실무적으로 보면

이 단계가 끝나면 OpenSpec을 "문서 관리 방식"으로 쓸 준비가 된 것이다. 아직 기능 명세가 생긴 것은 아니다.

## 2. 프로젝트 파악: `$openspec-onboard`

### 주요 산출물

- 명시적 고정 파일이 항상 생기는 것은 아님
- 필요 시 OpenSpec 설정, 프로젝트 맥락 메모, 온보딩 결과가 추가됨

### 이 산출물의 의미

이 단계는 새 기능을 만드는 단계가 아니라, OpenSpec이 현재 레포를 어떤 종류의 프로젝트로 봐야 하는지 이해시키는 단계다.

예를 들어 아래 같은 맥락을 정리할 수 있다.

- 이 프로젝트가 greenfield인지 brownfield인지
- 어떤 문서가 기준선인지
- 어떤 capability 단위로 spec을 나누는 게 맞는지
- 어떤 워크플로우를 기본으로 쓸지

### 실무적으로 보면

기존 레포에 OpenSpec을 붙일 때 유용하다. TCI처럼 이미 설계 문서와 요구사항 문서가 많은 프로젝트에서는 온보딩 없이 바로 propose를 시작하면 capability 경계가 흔들릴 수 있다.

## 3. 탐색: `$openspec-explore`

### 주요 산출물

- 보통 새 파일을 강제로 만들지 않음
- 필요하면 조사 메모나 외부 문서 정리본을 수동으로 남김

### 이 산출물의 의미

이 단계는 구현도 아니고 proposal 확정도 아니다. 말 그대로 생각을 정리하는 단계다. 문제를 쪼개고, 기존 코드나 요구사항을 읽고, 어떤 capability로 나눌지 감을 잡는 데 목적이 있다.

### 예시

- 요구사항 문서에서 특정 기능 범위 재해석
- 기존 C4 다이어그램이나 PRD 검토
- 구현 전에 데이터 모델 초안 탐색

### 실무적으로 보면

OpenSpec에서 `explore`는 꼭 파일을 만들지 않아도 된다. 하지만 팀에서 나중에 참고하려면 조사 결과를 별도 `research.md` 같은 문서로 남기는 편이 좋다.

## 4. 변경안 자동 생성: `$openspec-propose`

### 주요 산출물

- `openspec/changes/<change-name>/proposal.md`
- `openspec/changes/<change-name>/design.md`
- `openspec/changes/<change-name>/tasks.md`
- `openspec/changes/<change-name>/specs/<capability>/spec.md`
- `openspec/changes/<change-name>/.openspec.yaml`

### 이 산출물의 의미

이 단계는 OpenSpec의 핵심이다. 사용자가 "무엇을 바꾸고 싶은지"를 설명하면, OpenSpec은 그 변경을 하나의 `change`로 만들고 구현 전까지 필요한 문서를 한 번에 생성한다.

- `proposal.md`: 왜 이 변경이 필요한지
- `design.md`: 어떻게 구현할지
- `tasks.md`: 어떤 순서로 구현할지
- `changes/.../specs/**`: 어떤 capability 요구사항이 추가/수정/삭제되는지
- `.openspec.yaml`: change 메타데이터

### 예시

```text
openspec/changes/add-git-repo-target-filtering/
  .openspec.yaml
  proposal.md
  design.md
  tasks.md
  specs/
    git-repository-connection/
      spec.md
    repository-target-selection/
      spec.md
    repository-scope-filtering/
      spec.md
```

### 실무적으로 보면

Spec Kit의 `specify -> plan -> tasks`를 더 가볍게 한 번에 묶은 느낌으로 이해하면 쉽다. 다만 OpenSpec은 여기서도 baseline spec이 아니라 `change delta`를 만든다는 점이 핵심 차이다.

## 5. 수동 change 골격 생성: `$openspec-new-change`

### 주요 산출물

- `openspec/changes/<change-name>/`
- `.openspec.yaml`

### 이 산출물의 의미

`propose`가 자동으로 문서를 채워 주는 경로라면, `new`는 change 디렉터리만 먼저 만드는 수동 시작점이다. 복잡한 brownfield 변경이거나, 문서를 사람이 더 강하게 통제하고 싶을 때 쓴다.

### 실무적으로 보면

프로젝트 운영자가 미리 change 이름과 구조를 잡아 놓고, 이후 `continue`로 문서를 채우는 흐름에 적합하다.

## 6. 변경안 이어쓰기: `$openspec-continue-change`, `$openspec-ff-change`

### 주요 산출물

- 기존 `proposal.md`, `design.md`, `tasks.md`, `specs/**` 갱신

### 이 산출물의 의미

이 단계는 새 파일을 만드는 것보다 기존 change를 이어서 다듬는 역할에 가깝다.

- `continue`: 사람이 방향을 보며 계속 작성
- `ff`: 비교적 빠르게 현재 상태를 보강

### 실무적으로 보면

실제 프로젝트에서는 변경안이 한 번에 완성되지 않는 경우가 많다. 이 단계의 산출물은 "새 문서"보다 "기존 change 문서의 버전 상승"이라고 보는 편이 정확하다.

## 7. 구현: `$openspec-apply-change`

### 주요 산출물

- 코드 변경
- 테스트 코드
- 필요 시 프로젝트 문서 갱신
- change 내부 작업 체크 상태 갱신

### 이 산출물의 의미

이 단계부터는 OpenSpec이 문서 도구를 넘어 구현 워크플로우로 들어간다. 입력은 change 폴더의 문서들이고, 출력은 실제 코드와 테스트다.

OpenSpec 기준으로 보면 이 단계의 핵심은 "tasks를 따라 구현하고, 구현 결과를 change와 연결하는 것"이다.

### 실무적으로 보면

Spec Kit의 `$speckit-implement`와 비슷하게 볼 수 있지만, OpenSpec은 구현 전에 delta spec이 이미 change 안에 묶여 있다는 차이가 있다. 즉 "기존 시스템에 대한 변경 의도"가 더 직접적으로 연결된다.

## 8. 검증: `$openspec-verify-change`

### 주요 산출물

- 검증 결과 요약
- 실패 항목 또는 누락 항목 확인 결과
- 필요 시 수정된 `tasks.md` 또는 보강된 change 문서

### 이 산출물의 의미

이 단계는 구현이 끝났는지 보는 게 아니라, 구현이 change 문서와 맞는지 확인하는 단계다.

검증 관점 예시:

- spec 요구사항이 실제 구현에 반영되었는가
- design에서 약속한 구조가 크게 깨지지 않았는가
- tasks가 빠짐없이 처리되었는가
- archive할 만큼 change 품질이 충분한가

### 실무적으로 보면

이 단계를 생략하면 OpenSpec은 단순 문서 생성기로 끝나기 쉽다. verify가 있어야 문서와 코드의 정합성이 맞는지 한 번 더 걸러낼 수 있다.

## 9. 기준선 동기화: `$openspec-sync-specs`

### 주요 산출물

- 정리되거나 보강된 `openspec/specs/`
- capability 구조 정돈 결과

### 이 산출물의 의미

이 단계는 change 문서와 baseline spec 사이의 정렬을 돕는다. 프로젝트가 오래 가면 capability 이름, spec 폴더 구조, delta 적용 관점이 어지러워질 수 있는데, sync는 그 간극을 줄이는 역할을 한다.

### 실무적으로 보면

작은 프로젝트에서는 바로 archive로 넘어가도 되지만, capability가 많아지면 sync 단계가 baseline 품질 유지에 도움이 된다.

## 10. 기준선 반영과 종료: `$openspec-archive-change`

### 주요 산출물

- 갱신된 `openspec/specs/<capability>/spec.md`
- archive 처리된 change 상태
- 필요 시 archive 기록 또는 정리 결과

### 이 산출물의 의미

archive는 change를 닫는 단계다. 여기서 중요한 것은 change 폴더 자체보다, 그 change의 결과가 baseline spec으로 반영된다는 점이다.

즉, archive 이후에는 아래 상태가 된다.

- `changes/<name>/`는 완료된 변경안
- `specs/`는 새로운 현재 기준선

### 예시

변경 전:

```text
openspec/specs/
  repo-sync/spec.md

openspec/changes/add-git-repo-target-filtering/
  specs/repository-target-selection/spec.md
```

archive 후:

```text
openspec/specs/
  repo-sync/spec.md
  repository-target-selection/spec.md
  repository-scope-filtering/spec.md
```

### 실무적으로 보면

OpenSpec에서 archive는 단순 폴더 정리가 아니다. "이 변경이 이제 제안안이 아니라 현재 시스템의 공식 규격이 되었다"는 선언에 가깝다.

## 11. 일괄 종료: `$openspec-bulk-archive-change`

### 주요 산출물

- 여러 change의 archive 결과
- 정리된 `openspec/specs/`

### 이 산출물의 의미

개별 archive를 반복하기보다, 여러 완료된 change를 한 번에 정리하는 운영용 단계다. 팀 단위로 여러 변경안을 묶어 기준선에 반영할 때 쓸 수 있다.

### 실무적으로 보면

기능 수가 많아질수록 운영 효율에는 도움이 되지만, 작은 프로젝트에서는 개별 archive가 더 안전하다.

## OpenSpec 산출물 구조를 읽는 법

### 1. `proposal.md`는 왜 필요한가

이 문서는 "왜 바꾸는가"를 고정한다. 나중에 구현이 커졌을 때 scope creep를 막는 기준점이 된다.

### 2. `design.md`는 왜 필요한가

이 문서는 "어떻게 바꿀 것인가"를 고정한다. 데이터 모델, 컴포넌트 경계, 기술 선택 이유가 여기에 들어간다.

### 3. `tasks.md`는 왜 필요한가

이 문서는 change를 실행 가능한 단위로 쪼갠다. 구현 단계에서 AI나 개발자가 어디서부터 손대야 하는지 알려 주는 실무 체크리스트다.

### 4. `changes/.../specs/**`는 왜 필요한가

이 문서는 가장 중요하다. proposal과 design이 설명 문서라면, 여기 있는 spec은 실제 요구사항 계약이다. archive 이후에는 이 내용이 baseline spec으로 들어간다.

## Spec Kit과 비교하면 어디가 다른가

| 구분 | Spec Kit | OpenSpec |
| --- | --- | --- |
| 기준 철학 | 명세 먼저 작성 후 구현 | 변경 제안을 기준선 대비 delta로 관리 |
| 주요 작업 단위 | feature spec | change |
| 핵심 문서 흐름 | `spec -> plan -> tasks` | `proposal -> delta spec -> design -> tasks` |
| 기준선 관리 | 기능 문서 중심 | baseline spec vs change 분리 |
| brownfield 적합성 | 가능하지만 추가 설계 필요 | 기본적으로 강함 |

## 처음 쓰는 사람에게 추천하는 최소 경로

처음에는 모든 단계를 다 쓸 필요가 없다. 현재 TCI Codex 환경 기준으로는 아래 경로만 이해해도 충분하다.

1. `init`
2. `onboard`
3. `explore`
4. `propose`
5. `apply`
6. `verify`
7. `archive`

여기서 `init`은 CLI 단계이고, 나머지는 현재 Codex에서 직접 보이는 OpenSpec skill로 이어서 사용할 수 있다.

## 한 번에 기억할 핵심만 다시 요약

- `openspec/specs/`는 현재 기준선이다.
- `openspec/changes/`는 아직 제안 중인 변경 묶음이다.
- `proposal`, `design`, `tasks`는 change를 구현 가능하게 만드는 보조 문서다.
- 진짜 계약은 `changes/.../specs/**`의 delta requirement다.
- `archive`가 끝나야 그 변경이 baseline spec이 된다.

즉 OpenSpec의 단계별 산출물은 "문서를 많이 만드는 것"이 목적이 아니라, `현재 기준선`과 `제안 중인 변경`을 섞지 않고 추적 가능한 상태로 관리하기 위한 장치라고 보면 된다.
