# OpenSpec 단계별 산출물 발표용 요약

- 문서 목적: 팀 공유 자리에서 `티켓 시스템 연동` 기능을 예시로 OpenSpec 워크플로우와 산출물의 의미를 한눈에 설명하기 위한 발표 보조 문서
- 전제: 실제 산출물 예시는 라이브로 직접 보여주고, 이 문서는 "지금 보고 있는 파일이 왜 필요한가"를 빠르게 이해시키는 데 집중

## 먼저 핵심만

OpenSpec의 산출물은 전부 같은 목적을 가진다. 아이디어를 바로 구현하지 않고, `무엇을 왜 바꿀지 → 무엇이 달라질지 → 어떻게 구현할지 → 실제로 반영됐는지`를 change 단위 문서로 고정하는 것이다.

이번 발표에서는 [tci-final-feature-list.md](../tci-final-feature-list.md)의 `티켓 시스템 연동` 기능을 예시로 본다.

- Jira OAuth/API 기반 연동
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크

발표에서는 아래 흐름만 이해하면 충분하다.

- `explore`: 범위와 capability를 정리
- `propose` 또는 `new-change + ff-change`: change 문서 묶음 생성
- `apply-change`: 코드와 테스트로 반영
- `verify-change`: 문서와 구현 정합성 점검
- `archive-change`: 완료된 change를 기준선 spec으로 반영

## 전체 흐름 한눈에 보기

| 단계 | 대표 산출물 | 한 줄 의미 | 시연 때 팀원이 봐야 할 것 | 다음 단계로 넘기는 것 |
| --- | --- | --- | --- | --- |
| `explore` | 보통 고정 파일 없음 | 기능 범위와 capability 감 잡기 | 어떤 변경 단위로 나눌지 | change 방향 |
| `propose` | `proposal.md`, `design.md`, `tasks.md`, delta `spec.md` | change 문서를 한 번에 생성 | 왜 바꾸는지와 무엇이 달라지는지 | 구현 전 change 패키지 |
| `new-change` | `changes/<name>/`, `.openspec.yaml` | change 골격만 먼저 생성 | change 이름과 작업 단위 | 수동 작성 시작점 |
| `ff-change` | 갱신된 `proposal.md`, `design.md`, `tasks.md`, delta `spec.md` | 기존 change를 빠르게 채움 | 문서 묶음이 한 번에 채워짐 | 구현 전 change 패키지 |
| `continue-change` | 기존 change 문서 갱신 | change를 단계별로 이어서 다듬음 | 빠진 문서가 어떻게 보강되는지 | 더 완성된 change |
| `apply-change` | 코드, 테스트, 문서 변경 | change를 실제 구현으로 반영 | 문서가 코드로 바뀐 결과 | 구현 결과 |
| `verify-change` | 검증 결과, 필요 시 갱신된 `tasks.md` | 문서와 구현이 맞는지 확인 | 요구사항 누락과 작업 완료 여부 | archive 가능 여부 |
| `archive-change` | 갱신된 baseline `spec.md` | 완료된 change를 현재 기준선으로 반영 | change가 공식 규격이 되는 순간 | 새 기준선 |

## 발표에서는 이렇게 보면 된다

발표 중에는 모든 워크플로우를 같은 길이로 설명할 필요가 없다. 아래 우선순위로 보면 된다.

### 꼭 보여줄 워크플로우

- `propose`
- `apply-change`
- `verify-change`
- `archive-change`

### 짧게만 언급할 워크플로우

- `explore`
- `new-change`
- `ff-change`
- `continue-change`

## 추천 흐름 두 가지

### 1. 빠른 생성 경로

`explore → propose → apply-change → verify-change → archive-change`

이 경로는 티켓 시스템 연동처럼 범위가 어느 정도 잡혀 있을 때 가장 설명하기 쉽다. 발표 시연도 이 흐름이 가장 직관적이다.

### 2. 통제형 경로

`explore → new-change → ff-change 또는 continue-change → apply-change → verify-change → archive-change`

이 경로는 change 이름과 구조를 먼저 고정하고, 문서를 단계적으로 채우고 싶을 때 쓴다. 범위가 흔들리기 쉬운 기능이면 이 방식이 더 안전하다.

## 단계별 설명

## 1. `explore`

### 산출물

- 고정 산출물 없음: 범위 탐색 단계라 항상 파일이 생기지는 않음
- 조사 메모: 필요하면 capability 후보나 범위 판단 근거를 따로 남길 수 있음

### 의미

이 단계는 문서를 확정하는 단계가 아니다. 티켓 시스템 연동을 하나의 change로 볼지, 인증과 동기화를 나눌지, 어떤 capability가 필요한지 감을 잡는 단계다.

### 시연 때 포인트

- `티켓 시스템 연동` 범위를 어떻게 나눌지
- Jira 1차 지원인지, 다른 티켓 시스템까지 포함할지
- capability를 몇 개로 나눌지

### 한 줄로 정리

`explore`는 proposal을 쓰기 전에 change 경계를 잡는 단계다.

## 2. `propose`

### 산출물

- `proposal.md`: 왜 이 변경이 필요한지와 범위, 비범위를 정리하는 문서
- `design.md`: 인증, 동기화, 필터링, 수집 구조를 설명하는 설계 문서
- `tasks.md`: 구현 순서와 작업 단위를 정리한 실행 계획 문서
- `spec.md`: baseline 대비 추가되거나 수정되는 요구사항을 적는 delta spec
- `.openspec.yaml`: change 이름과 상태를 담는 메타데이터 파일

### 의미

OpenSpec의 핵심 단계다. 티켓 시스템 연동에 대해 설명하면, 이 단계에서 "왜 이 기능이 필요한지", "무엇이 바뀌는지", "어떻게 구현할지", "무슨 작업을 해야 하는지"가 한 번에 묶인다.

### 시연 때 포인트

- `proposal.md`: 왜 필요한지와 범위
- `spec.md`: 어떤 요구사항이 추가되거나 수정되는지
- `design.md`: 인증, 필터링, 메타데이터 수집 구조
- `tasks.md`: 구현 작업 순서

### 한 줄로 정리

`propose`는 change 문서 패키지를 한 번에 만드는 단계다.

## 3. `new-change`

### 산출물

- `openspec/changes/<change-name>/`: 이 변경에 속한 문서가 모이는 작업 디렉터리
- `.openspec.yaml`: change 메타데이터를 담는 기본 설정 파일

### 의미

자동으로 내용을 많이 채우기보다, change 틀만 먼저 만드는 단계다. 티켓 시스템 연동처럼 인증, 프로젝트 선택, 필터링, 메타데이터 수집이 섞여 있을 때 구조를 먼저 고정하고 싶다면 유용하다.

### 시연 때 포인트

- change 이름이 어떻게 잡히는지
- change 폴더가 baseline spec과 분리되어 있다는 점

### 한 줄로 정리

`new-change`는 문서를 쓰기 전 change 작업장을 만드는 단계다.

## 4. `ff-change`

### 산출물

- `proposal.md`: change의 목적과 범위를 빠르게 채운 문서
- `design.md`: 구현 구조와 기술 접근을 빠르게 채운 문서
- `tasks.md`: 실행 순서를 바로 볼 수 있게 정리한 작업 목록
- `spec.md`: baseline 대비 요구사항 변화를 반영한 delta spec

### 의미

이미 만든 change 골격에 필요한 planning artifact를 빠르게 채우는 단계다. 발표에서는 `propose`의 대안 경로 정도로 설명하면 충분하다.

### 시연 때 포인트

- `new-change` 후 비어 있던 change가 문서 묶음으로 채워지는 점
- proposal, design, tasks, spec이 같이 생성되는 점

### 한 줄로 정리

`ff-change`는 수동으로 만든 change를 빠르게 설계 패키지로 완성하는 단계다.

## 5. `continue-change`

### 산출물

- 갱신된 `proposal.md`: 범위나 비범위 변경이 반영된 문서
- 갱신된 `design.md`: 인증, 필터링, 동기화 구조 보강이 반영된 문서
- 갱신된 `tasks.md`: 추가되거나 수정된 구현 작업이 반영된 문서
- 갱신된 `spec.md`: 새 요구사항 해석이 반영된 delta spec

### 의미

change 문서가 한 번에 끝나지 않았을 때 이어서 보강하는 단계다. 티켓 시스템 연동처럼 연동 범위나 수집 항목이 나중에 바뀔 수 있는 기능에서 유용하다.

### 시연 때 포인트

- 빠진 문서가 보강되는 모습
- 기존 change를 버리지 않고 점진적으로 다듬는 방식

### 한 줄로 정리

`continue-change`는 change를 다시 쓰는 것이 아니라 이어서 다듬는 단계다.

## 6. `apply-change`

### 산출물

- 실제 코드: change 문서를 기준으로 구현된 기능 결과물
- 테스트 코드: 요구사항과 설계가 의도대로 동작하는지 검증하는 코드
- 반영된 프로젝트 문서: 구현 결과에 맞춰 갱신된 운영 문서나 설명 문서
- 갱신된 change 상태: 완료된 task나 진행 상태가 반영된 change 문서

### 의미

앞에서 만든 change 문서를 실제 구현으로 반영하는 단계다. 티켓 시스템 연동 예시에서는 OAuth/API 인증 처리, 프로젝트 선택 UI나 설정, 필터링 로직, 이슈 메타데이터 수집 코드가 이 단계에서 나온다.

### 시연 때 포인트

- 문서가 코드로 어떻게 이어지는지
- `tasks.md`를 기준으로 구현이 진행되는지
- 테스트가 함께 생기는지

### 한 줄로 정리

`apply-change`는 change 문서를 코드와 테스트로 바꾸는 단계다.

## 7. `verify-change`

### 산출물

- 검증 결과: 구현이 change 문서와 맞는지 정리한 점검 결과
- 실패 항목 또는 누락 항목: 빠진 요구사항이나 미완료 작업 목록
- 갱신된 `tasks.md`: 검증 후 다시 처리해야 할 작업이 반영된 문서
- 보강된 change 문서: 필요 시 proposal, design, spec에 수정이 반영된 문서

### 의미

구현이 끝났는지 보는 단계가 아니라, 구현이 `proposal`, `design`, `spec`, `tasks`와 맞는지 확인하는 단계다.

### 시연 때 포인트

- 인증 요구사항이 실제로 반영됐는지
- 필터링 조건이 빠지지 않았는지
- 메타데이터 수집 범위가 spec과 맞는지
- 미완료 task가 남아 있지 않은지

### 한 줄로 정리

`verify-change`는 구현 결과를 change 문서와 대조하는 단계다.

## 8. `archive-change`

### 산출물

- 갱신된 baseline `spec.md`: 완료된 change 내용이 반영된 현재 기준선 규격
- archive 처리된 change: 제안 단계가 끝난 이력으로 남는 change 묶음

### 의미

완료된 change를 현재 기준선으로 반영하는 단계다. 티켓 시스템 연동이 이 단계까지 오면, 더 이상 "제안 중인 변경"이 아니라 "현재 시스템이 따라야 하는 공식 규격"이 된다.

### 시연 때 포인트

- `changes/`에 있던 문서가 `specs/` 기준선으로 반영되는 점
- change가 공식 규격으로 승격되는 순간

### 한 줄로 정리

`archive-change`는 완료된 change를 baseline spec으로 올리는 단계다.

## 산출물끼리 어떻게 이어지나

티켓 시스템 연동 기능은 보통 아래 순서로 이어진다.

1. `explore`에서 범위와 capability를 잡는다
2. `propose` 또는 `new-change + ff-change`로 change 문서를 만든다
3. `apply-change`로 실제 코드와 테스트를 만든다
4. `verify-change`로 문서와 구현 정합성을 점검한다
5. `archive-change`로 baseline spec에 반영한다

즉, 앞 단계 산출물은 다음 단계의 입력이다.

## 팀원이 꼭 기억하면 좋은 포인트

- OpenSpec의 핵심 단위는 feature가 아니라 `change`
- `proposal.md`는 왜 바꾸는지
- delta `spec.md`는 무엇이 달라지는지
- `design.md`는 어떻게 구현할지
- `tasks.md`는 어떤 작업을 할지
- `archive-change`가 끝나야 그 변경이 공식 기준선이 됨

## 티켓 시스템 연동 시연용 복붙 프롬프트

아래 프롬프트는 [tci-final-feature-list.md](../tci-final-feature-list.md)의 `티켓 시스템 연동` 기능을 기준으로 잡았다.

### 1. `explore`

```text
$openspec-explore
TCI의 "티켓 시스템 연동" 기능을 OpenSpec change로 정리하기 전에 범위와 capability를 먼저 탐색해줘.

기능 설명:
- Jira 등 외부 티켓 관리 시스템과 연동하여 코드 외 업무 맥락 정보를 수집하고 분석에 활용한다

상세 기능:
- Jira OAuth/API 기반 연동
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크

요청사항:
- 이 기능을 OpenSpec에서 어떤 capability들로 나누면 좋을지 제안해줘
- 1차 범위와 후속 범위를 구분해줘
- proposal 단계로 넘기기 전에 모호한 점이 무엇인지 짚어줘
```

### 2. `propose`

```text
$openspec-propose
TCI의 "티켓 시스템 연동" 기능에 대한 OpenSpec change를 작성해줘.

기능 설명:
- Jira 등 외부 티켓 관리 시스템과 연동하여 코드 외 업무 맥락 정보를 수집하고 분석에 활용한다

상세 기능:
- Jira OAuth/API 기반 연동
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크

요청사항:
- change 이름을 제안해줘
- proposal.md에는 문제, 범위, 비범위, 기대 효과를 포함해줘
- design.md에는 인증, 동기화, 필터링, 메타데이터 수집 흐름을 포함해줘
- tasks.md에는 구현 가능한 작업 순서를 넣어줘
- specs는 baseline 대비 delta 형태로 작성해줘
- 지금 단계에서는 Jira를 1차 지원 대상으로 가정해도 된다
```

### 3. `new-change`

```text
$openspec-new-change
TCI의 "티켓 시스템 연동" 기능을 위한 새 change를 만들어줘.

change 이름은 티켓 시스템 연동과 Jira 1차 지원 범위가 드러나게 제안해줘.
이 change는 아래 범위를 다룬다.

- Jira OAuth/API 기반 연동
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크
```

### 4. `ff-change`

```text
$openspec-ff-change
방금 만든 티켓 시스템 연동 change를 기준으로 planning artifact를 한 번에 채워줘.

반영할 범위:
- Jira OAuth/API 기반 연동
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크

특히 아래가 드러나게 해줘.
- proposal.md에는 1차 범위와 비범위
- design.md에는 인증과 동기화 구조
- tasks.md에는 구현 순서
- specs에는 baseline 대비 ADDED 또는 MODIFIED 요구사항
```

### 5. `continue-change`

```text
$openspec-continue-change
티켓 시스템 연동 change를 이어서 보강해줘.

특히 아래 내용을 기존 change 문서에 반영해줘.
- 프로젝트/스페이스 선택 범위가 워크스페이스 기준인지 사용자 기준인지
- 이슈 유형과 상태 필터링 규칙
- 수집 메타데이터에 포함되는 항목과 제외되는 항목
- 인증 실패, 권한 부족, 만료 토큰 처리 원칙

새 change를 만들지 말고 기존 proposal, design, tasks, specs를 갱신하는 방식으로 진행해줘.
```

### 6. `apply-change`

```text
$openspec-apply-change
티켓 시스템 연동 change의 문서를 기준으로 실제 구현을 진행해줘.

우선순위:
- Jira OAuth/API 기반 인증 처리
- 프로젝트/스페이스 선택
- 이슈 유형 및 상태 필터링
- 이슈 메타데이터 수집
  - 제목
  - 설명
  - 작성자
  - 상태
  - 링크

요청사항:
- tasks.md 순서를 따르되 미완료 task 중심으로 진행해줘
- 관련 테스트도 함께 추가해줘
- 구현 중 문서와 충돌하는 점이 있으면 표시해줘
```

### 7. `verify-change`

```text
$openspec-verify-change
티켓 시스템 연동 change가 proposal, design, tasks, specs에 맞게 구현되었는지 검증해줘.

특히 아래를 중점적으로 확인해줘.
- 인증 방식이 요구사항에 맞는가
- 프로젝트/스페이스 선택이 설계 의도와 맞는가
- 이슈 유형 및 상태 필터링이 빠지지 않았는가
- 메타데이터 수집 범위가 spec과 맞는가
- tasks.md에 남은 작업이 있는가
- archive 가능한 수준인지 판단해줘
```

### 8. `archive-change`

```text
$openspec-archive-change
티켓 시스템 연동 change를 archive해줘.

archive 전에 아래를 다시 확인해줘.
- verify 결과 치명적 누락이 없는가
- baseline spec으로 반영해도 되는가
- change 문서가 현재 기준선으로 승격될 준비가 되었는가
```

## 같이 보면 좋은 문서

- 입문 설명: [SDD를 모르는 팀원을 위한 OpenSpec 소개.md](./SDD%EB%A5%BC%20%EB%AA%A8%EB%A5%B4%EB%8A%94%20%ED%8C%80%EC%9B%90%EC%9D%84%20%EC%9C%84%ED%95%9C%20OpenSpec%20%EC%86%8C%EA%B0%9C.md)
- 상세 설명: [openspec 단계별 산출물 설명 압축본.md](./openspec%20%EB%8B%A8%EA%B3%84%EB%B3%84%20%EC%82%B0%EC%B6%9C%EB%AC%BC%20%EC%84%A4%EB%AA%85%20%EC%95%95%EC%B6%95%EB%B3%B8.md)
- 로컬 가이드: [codex-cli 기준 openspec 사용 가이드.md](./codex-cli%20%EA%B8%B0%EC%A4%80%20openspec%20%EC%82%AC%EC%9A%A9%20%EA%B0%80%EC%9D%B4%EB%93%9C.md)
