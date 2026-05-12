# SpecKit 기반 TCI 프로젝트 산출물 구조

## 문서 목적

이 문서는 SpecKit 기반 TCI 프로젝트에서 주요 산출물이 어디에 위치하고, 어떤 기준으로 변경되어야 하는지 정리한다. Harness는 이 구조를 검사하고 Gate로 강제하는 역할을 맡지만, 산출물 위치와 변경 기준 자체는 Harness 내부 규칙이 아니라 TCI 전체 프로젝트 운영 기준으로 다룬다.

Agent Harness의 내부 구조와 PR Gate 실행 방식은 별도 운영 기준으로 다루고, 이 문서는 Harness가 검사해야 할 TCI 프로젝트 산출물의 배치와 책임을 다룬다.

이 문서에서 쓰는 주요 용어는 다음처럼 해석한다.

| 용어 | 의미 |
| --- | --- |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름 |
| Feature 운영 등록부 | Feature별 산출물 경로, 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역을 연결하는 `feature-registry/<feature-id>.yml` |
| 검증 절차 | 구현자가 실행하거나 운영자가 따라 할 예정 검증 기준 |
| 완료 근거 | 실제로 실행한 검증, 생략 사유, 승인된 잔여 위험을 남긴 기록 |
| PR Gate | main 병합 전에 산출물 누락, 범위 위반, 민감 정보 노출, 검토 누락을 확인하는 자동 검사와 검토 흐름 |
| Harness | Feature 운영 등록부와 산출물을 읽고 PR Gate를 실행하는 운영 레이어 |

## 문서 범위

이 문서의 결정 범위는 다음과 같다.

- TCI 전체 프로젝트에서 `apps/`, `services/`, `specs/`, `evidence/`, `feature-registry/`, `boundary-contracts/`, `docs/`가 맡는 역할
- SpecKit 기본 경로를 유지하는 이유
- Feature ID 기준 산출물 생성과 갱신 흐름
- Feature 전용 계약과 공유 계약의 분리 기준
- `spec.md`, `plan.md`, `tasks.md`, `quickstart.md`, `contracts/` 변경 시 함께 확인할 기준
- evidence 표준 위치와 기본 항목
- 실행 산출물과 문서 산출물의 위치 기준

이 문서가 정하지 않는 것은 다음과 같다.

- 개별 Feature의 상세 요구사항
- Harness 내부 디렉터리 구조
- Feature 운영 등록부의 전체 필드 schema와 Gate 규칙
- app, service 내부 코드 작성 규칙
- 테스트 프레임워크별 작성 방식
- CI 구현 방식

# 전체 산출물 구조

## 기본 구조

TCI 프로젝트의 산출물은 제품 코드, Feature별 SpecKit 산출물, 완료 판단 근거, Feature 운영 등록부, 공유 경계 기준, 장기 문서로 나뉜다.

Feature 산출물은 보통 다음 순서로 생긴다.

1. Feature ID를 정하고 `feature-registry/<feature-id>.yml` 초안을 만든다
2. SpecKit으로 `specs/<feature-id>/` 산출물을 만든다
3. API, event, storage, tracing 같은 협업 경계가 필요하면 `specs/<feature-id>/contracts/`에 Feature 전용 계약을 둔다
4. 구현 전 `quickstart.md`에 예정 검증 절차를 정리한다
5. 구현 중 범위나 계약 의미가 바뀌면 `plan.md`, `tasks.md`, `quickstart.md`, Feature 운영 등록부를 함께 갱신한다
6. 구현 또는 PR 준비 중 `evidence/<feature-id>/verification.md`에 실제 검증 결과와 잔여 위험을 남긴다
7. PR Gate는 Feature 운영 등록부와 산출물을 읽어 누락과 범위 위반을 확인한다

```text
tci-platform/
├─ apps/                         # 사용자-facing 애플리케이션
│  ├─ core-api/                  # 제품 API
│  └─ web-console/               # 운영 콘솔 UI
├─ services/                     # 독립 실행 내부 서비스
│  ├─ analyzer/                  # 분석 작업
│  └─ workers/                   # 비동기 worker
├─ specs/                        # Feature별 SpecKit 산출물
│  └─ <feature-id>/              # Feature ID 단위 작업 공간
│     ├─ spec.md                 # 요구사항과 성공 기준
│     ├─ plan.md                 # 구현 전략과 위험 판단
│     ├─ research.md             # 선택지와 결정 근거
│     ├─ data-model.md           # 도메인 모델과 상태 변화
│     ├─ quickstart.md           # 예정 검증 절차
│     ├─ tasks.md                # 작업 순서와 병렬화 기준
│     ├─ checklists/             # 요구사항 품질 검사
│     └─ contracts/              # Feature 전용 협업 경계
├─ evidence/                     # 완료 판단 근거
│  └─ <feature-id>/
│     └─ verification.md         # 실제 검증 결과와 잔여 위험
├─ feature-registry/             # Feature별 운영 등록부
│  └─ <feature-id>.yml           # 쓰기 범위와 Gate 기준 연결
├─ boundary-contracts/           # Feature를 넘는 공유 경계 기준
│  └─ shared/                    # 여러 Feature가 함께 쓰는 계약
└─ docs/                         # 장기 유지 문서
   ├─ architecture/              # 구조 설명
   └─ adr/                       # 되돌리기 어려운 결정 기록
```

## 책임 분리

| 위치 | 책임 |
| --- | --- |
| `apps/` | 사용자와 직접 맞닿는 애플리케이션 |
| `services/` | 독립 실행 성격이 강한 내부 서비스와 worker |
| `specs/<feature-id>/` | Feature별 요구사항, 설계 판단, 작업 목록, 검증 절차 |
| `specs/<feature-id>/contracts/` | 해당 Feature에서 사용하는 API, event, storage, tracing, 예제 데이터 기준 |
| `evidence/<feature-id>/verification.md` | 완료 판단 근거, 실행한 검증, 잔여 위험, 증거 링크 |
| `feature-registry/<feature-id>.yml` | Feature ID, 산출물 경로, 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역 연결 |
| `boundary-contracts/shared/` | 여러 Feature가 공유하는 장기 경계 기준 |
| `docs/architecture/` | Feature를 넘어 유지되는 구조 설명 |
| `docs/adr/` | 되돌리기 어려운 결정의 배경과 대안 기록 |

제품 코드는 `apps/`와 `services/`에 둔다. 요구사항, 설계 판단, 검증 절차는 `specs/`에서 추적한다. 완료 판단 근거는 `evidence/`에 남긴다. Feature별 운영 데이터는 `feature-registry/`에 둔다. Harness는 이 구조를 읽고 변경 범위, 필수 문서, Gate를 검사한다.

Feature 운영 등록부는 한 번에 완성되는 파일이 아니다. Feature 접수 시 초안을 만들고, `plan.md`와 `tasks.md`가 안정되면 구현 가능한 상태로 갱신하며, PR 전에는 실제 변경 범위와 완료 근거를 기준으로 다시 맞춘다.

| 상태 | 시점 | 필수 정보 | Gate 의미 |
| --- | --- | --- | --- |
| `draft` | Feature ID를 정하고 작업을 접수한 직후 | Feature ID, `specs/` 경로, 임시 소유자 | Gate 차단 기준으로 쓰지 않고 추적 시작점으로만 사용 |
| `implementation-ready` | `plan.md`와 `tasks.md`로 구현 범위가 정리된 뒤 | 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역 후보, 필요한 검토자 | 구현 중 범위 이탈과 문서 누락을 확인하는 기준 |
| `completion-check` | PR 준비 또는 완료 판단 직전 | 실제 수정 범위, 갱신한 산출물, 공동 수정 영역 승인, 실행한 검증, 잔여 위험 | PR Gate가 누락, 범위 위반, 검토 누락을 확인하는 기준 |

이 문서는 등록부의 위치와 생명주기만 정하고, 전체 필드 schema와 Gate 규칙은 Harness 운영 기준에서 다룬다.

`docs/architecture/`와 `docs/adr/`는 모든 Feature에서 수정하지 않는다. 다음처럼 Feature를 넘어 오래 유지될 판단이 생길 때만 갱신한다.

- 여러 Feature가 따를 구조 원칙 변경
- worker, analyzer, API, UI 책임 경계 변경
- 인증 정보, 민감 정보, 외부 입력 같은 보안 경계 변경
- 공유 계약 또는 저장 모델 변경
- 되돌리기 어려운 기술 선택이나 운영 정책 결정

# SpecKit 산출물 위치

## 기본 경로 유지

SpecKit 산출물은 `specs/<feature-id>/`를 정식 작업 공간으로 둔다. SpecKit 경로를 그대로 쓰는 이유는 도구의 기본값을 팀 규칙의 출발점으로 삼기 위해서다. Harness나 팀 규칙이 산출물 위치를 다시 정의하기보다, SpecKit이 만드는 경로를 읽고 그 위에 검증 기준을 얹는 편이 안정적이다.

SpecKit 기본 경로를 유지하면 다음 이점이 있다.

- SpecKit 템플릿과 명령이 기대하는 상대 경로 유지
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md` 사이의 참조 관계 유지
- Agent가 읽어야 할 시작점 명확화
- Feature 산출물 검사 시 경로 변환 규칙 최소화
- SpecKit 업그레이드나 템플릿 변경 시 팀 커스텀 경로와 충돌 가능성 감소

## 산출물 매핑

| 산출물 | 표준 위치 | 생성과 갱신 기준 | 역할 |
| --- | --- | --- | --- |
| `spec.md` | `specs/<feature-id>/spec.md` | Feature 요구사항을 정리할 때 생성하고, 사용자 흐름이나 성공 기준이 바뀌면 갱신 | 사용자 요구와 성공 기준 |
| `plan.md` | `specs/<feature-id>/plan.md` | 구현 전략을 정할 때 생성하고, 기술 선택이나 위험 판단이 바뀌면 갱신 | 구현 전략, 기술 선택, 위험 판단 |
| `research.md` | `specs/<feature-id>/research.md` | 불확실한 선택지를 검토할 때 생성하고, 결정 근거가 바뀌면 갱신 | 불확실한 선택지와 결정 근거 |
| `data-model.md` | `specs/<feature-id>/data-model.md` | 도메인 모델이나 상태 변화가 필요한 Feature에서 생성하고, 저장 구조나 상태 의미가 바뀌면 갱신 | 도메인 모델과 상태 변화 |
| `quickstart.md` | `specs/<feature-id>/quickstart.md` | 검증 절차를 정할 때 생성하고, 테스트나 운영자 확인 절차가 바뀌면 갱신 | 사람이 따라 할 예정 검증 절차 |
| `tasks.md` | `specs/<feature-id>/tasks.md` | 구현 작업을 나눌 때 생성하고, 작업 순서나 병렬화 기준이 바뀌면 갱신 | 작업 순서와 병렬화 기준 |
| `checklists/` | `specs/<feature-id>/checklists/` | 요구사항 품질 검사가 필요할 때 생성하고, 요구사항 기준이 바뀌면 갱신 | 요구사항 품질 검사 |
| `contracts/` | `specs/<feature-id>/contracts/` | 협업 경계를 문서화해야 할 때 생성하고, API, event, storage, tracing 의미가 바뀌면 갱신 | 이 Feature의 경계 기준 |
| `verification.md` | `evidence/<feature-id>/verification.md` | 구현 또는 PR 준비 중 생성하고, 검증 결과나 잔여 위험이 바뀌면 갱신 | 실제 검증 결과, 증거 링크, 잔여 위험 |

# 계약 위치와 변경 기준

## Feature 전용 계약

Feature 하나에서만 쓰는 경계 기준은 `specs/<feature-id>/contracts/`를 기준 위치로 둔다. 프론트엔드와 백엔드가 같은 기능을 병렬 개발할 때도 이 경로를 기준으로 맞춘다.

`contracts/` 하위 디렉터리는 모든 Feature에 항상 만들지 않는다. 해당 Feature의 협업 경계를 문서화해야 할 때만 필요한 하위 항목을 둔다.

```text
specs/<feature-id>/contracts/
├─ api/
├─ events/
├─ storage/
├─ tracing/
└─ examples/
```

각 하위 디렉터리는 다음 기준으로 사용한다.

| 위치 | 사용 기준 | 대표 파일 예시 |
| --- | --- | --- |
| `api/` | Feature 전용 API 요청, 응답, 오류 응답 형식 기준 | `endpoints.md` |
| `events/` | Feature 전용 이벤트 본문과 메시지 기준 | `events.md` |
| `storage/` | 해당 Feature가 변경하거나 의존하는 저장 경계, migration 의도, 하위 호환 기준 | `migration-intent.md` |
| `tracing/` | Feature 전용 trace/span 이름과 속성 기준 | `spans.md` |
| `examples/` | Feature 전용 검증용 예제 데이터 | `examples.md` |

## 공유 계약

여러 Feature가 함께 쓰는 장기 기준은 `boundary-contracts/shared/`로 올린다. 이 위치는 Feature별 계약 복사본을 두는 곳이 아니라 제품 전체에서 반복 적용할 기준을 두는 곳이다.

```text
boundary-contracts/
└─ shared/
   ├─ api/
   ├─ events/
   ├─ mcp/
   ├─ storage/
   ├─ tracing/
   └─ examples/
```

공유 계약의 하위 디렉터리 역할은 다음과 같다.

| 위치 | 역할 | 대표 파일 예시 |
| --- | --- | --- |
| `api/` | 공통 오류 응답, 인증 헤더, 페이지 나누기 기준 | `error-response.md` |
| `events/` | 여러 worker와 analyzer가 함께 쓰는 이벤트 공통 구조와 메시지 규칙 | `event-envelope.md` |
| `mcp/` | 외부 Agent에게 공통으로 제공할 컨텍스트 묶음과 tool 입출력 기준 | `tool-contracts.md` |
| `storage/` | 여러 Feature가 공통으로 따르는 저장 정책, 산출물 저장 위치, 보존 기간, 호환성 기준 | `artifact-retention.md` |
| `tracing/` | 여러 Feature가 공유하는 trace 속성과 이름 기준 | `trace-attributes.md` |
| `examples/` | 여러 Feature가 함께 쓰는 공통 검증용 예제 데이터 | `shared-fixtures.md` |

## 공유 계약 승격 기준

Feature 전용 계약은 다음 조건을 만족할 때 `boundary-contracts/shared/`로 승격한다.

| 기준 | 의미 |
| --- | --- |
| 반복 사용 | 두 개 이상의 Feature가 같은 API 형식, 이벤트 공통 구조, trace 속성을 사용 |
| Feature와 독립된 의미 | 특정 Feature의 세부 요구가 아니라 제품 전체에서 같은 의미로 쓰임 |
| 장기 유지 필요 | 한 번 정하면 여러 release 동안 유지해야 하는 기준 |
| 공유 필요 확정 | 두 번째 사용처가 생겼거나 승인된 Feature 계획에서 같은 기준을 재사용하기로 확정됨 |
| 공통 언어 역할 | 팀이 같은 오류 형식, 이벤트 형식, trace 속성 이름으로 대화해야 함 |

공유 계약은 가능한 한 구현 전에 고정한다. 다만 실제 구현 중 두 번째 사용처가 확인되거나, 구현 뒤에 같은 기준을 반복 적용해야 한다는 사실이 드러날 수 있다. 이 경우에도 공유 계약으로 승격하기 전에는 영향 범위와 검증 기준을 먼저 정리해야 한다.

| 발견 시점 | 처리 기준 | 차단 기준 |
| --- | --- | --- |
| 구현 전 | `boundary-contracts/shared/`에 공유 기준을 먼저 만들고 Feature 전용 계약은 참조만 남김 | 공유 기준 책임자와 사용처 검토 없이 구현 착수 금지 |
| 구현 중 | 현재 Feature의 계약을 임시 기준으로 고정한 뒤, 두 번째 사용처와 함께 공유 계약 승격 여부를 결정 | 기존 구현과 새 사용처가 서로 다른 의미로 같은 이름을 쓰면 병합 보류 |
| 구현 후 | 반복 사용이 확인된 시점에 공유 계약으로 승격하고, 기존 Feature의 검증 절차와 완료 근거를 갱신 | 승격 후 기존 Feature의 검증 기준을 갱신하지 않으면 완료 처리 금지 |

Feature 전용 계약을 공유 계약으로 승격할 때는 다음 순서로 정리한다.

1. `boundary-contracts/shared/`에 공유 기준을 만들거나 기존 기준을 갱신한다
2. 기존 Feature 전용 계약에는 공유 기준 참조 또는 차이점만 남긴다
3. 영향받는 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md` 기준을 확인한다
4. 다른 Feature가 같은 계약을 참조하면 사용처 검증 범위를 함께 정리한다
5. 공유 계약 책임자 또는 책임 검토자의 승인 조건을 남긴다

## 계약 변경 처리

`contracts/` 변경은 협업 경계 변경으로 취급한다. 계약은 개발자 개인의 구현 세부사항이 아니라 프론트엔드, 백엔드, worker, analyzer, 테스트, evidence가 맞춰야 하는 기준이다. 따라서 계약 의미가 바뀌면 단순 문서 수정으로 처리하지 않는다.

계약 의미 변경에 해당하는 예시는 다음과 같다.

- API 요청 또는 응답 필드 추가, 제거, 이름 변경
- 필수 필드와 선택 필드 기준 변경
- 오류 응답 형식 변경
- 이벤트 본문 구조 변경
- DB table, column, 상태 전이 의미 변경
- trace/span 이름 또는 필수 속성 변경
- 검증용 예제 데이터의 의미 변경

Feature 내부에서만 쓰는 계약이라도 의미가 바뀌면 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md` 영향까지 함께 확인한다. 다른 개발자나 다른 Feature가 참조하는 계약이면 계약 변경 제안, 영향 범위 확인, 관련 작업 재분해, Gate 통과 흐름으로 처리한다. Gate 실패 처리 방식 자체는 Harness 운영 기준에서 다루지만, 이 문서는 어떤 산출물을 고쳐야 하는지까지 정한다.

다음 변경은 자동 검사만으로 완료 처리하지 않고 사람 검토를 함께 요구한다.

| 변경 | 필요한 검토 |
| --- | --- |
| 공유 계약 추가, 변경, 승격 | 계약 책임자 또는 영향받는 사용처 책임자 검토 |
| DB migration 의도 변경 | DB 책임자 검토와 실제 migration 파일 위치 확인 |
| 보안 경계 변경 | 보안 또는 아키텍처 책임자 검토 |
| 운영자 직접 확인 절차 변경 | 실제 수행자 또는 운영 책임자 확인 |
| 잔여 위험을 남긴 완료 판단 | Feature 책임자의 명시 승인 |

# Tracing 기준

## Feature 전용 tracing

Feature 전용 trace/span 기준은 `specs/<feature-id>/contracts/tracing/`에 둔다. 이 위치는 특정 Feature를 구현하고 운영할 때 어떤 작업 구간을 관찰해야 하는지 정하는 곳이다. OTel 설정 자체를 Feature마다 다르게 만든다는 뜻이 아니라, 같은 OTel 기반 위에서 어떤 작업 구간을 나눠 볼지 Feature별로 정한다는 뜻이다.

trace는 하나의 요청이나 작업 흐름 전체다. span은 그 흐름 안의 한 작업 구간이다. 예를 들어 “저장소 snapshot 생성”이라는 trace 안에는 “연결 정보 확인”, “원격 저장소 fetch”, “파일 tree 분석”, “산출물 저장”, “DB 기록” 같은 span이 들어갈 수 있다. 장애나 지연이 생겼을 때 span을 보면 어느 구간에서 문제가 생겼는지 좁힐 수 있다.

`specs/<feature-id>/contracts/tracing/spans.md`는 모든 Feature에 만들 필요가 없다. 이 파일은 운영 중 장애나 지연을 추적할 때 어떤 작업 구간을 봐야 하는지 정하는 문서다. 단순 UI 변경, 작은 validation 추가, API field 추가처럼 흐름이 짧은 Feature에는 과하다.

`spans.md`가 필요한 경우는 다음과 같다.

- API, worker, analyzer처럼 여러 컴포넌트를 지나는 Feature
- 비동기 job이나 queue 대기가 있는 Feature
- 외부 API, Git provider, 파일 처리처럼 실패 지점이 많은 Feature
- 성능 병목이나 장애 원인 추적이 운영상 중요한 Feature
- 기존 trace로는 어느 구간이 느린지 보기 어려운 Feature

필요한 Feature에서만 trace 이름, 주요 작업 구간, 필수 속성, 실패 상태 기록 방식을 정리한다.

예를 들어 Git 저장소 snapshot 생성 Feature는 다음처럼 볼 수 있다.

```text
trace: repository.snapshot.create

span: repository.connection.resolve
span: git.remote.fetch
span: repository.tree.scan
span: snapshot.metadata.build
span: snapshot.artifact.store
span: snapshot.db.persist
```

이 Feature에서는 Git provider 연결, fetch, 파일 분석, 산출물 저장, DB 기록 중 어느 구간에서 실패하거나 느려졌는지가 중요하다. 따라서 `workspace_id`, `connection_id`, `provider`, `commit_sha`, `snapshot_id`, `file_count`, `artifact_size_bytes` 같은 속성을 남기면 운영 중 원인을 좁히기 쉽다.

다른 Feature 유형은 코드블록을 반복하기보다 다음처럼 요약한다.

| Feature 유형 | trace 이름 | 주요 span | 권장 속성 |
| --- | --- | --- | --- |
| Git snapshot | `repository.snapshot.create` | 연결 확인, fetch, tree 분석, metadata 생성, 산출물 저장, DB 기록 | `workspace_id`, `connection_id`, `provider`, `commit_sha`, `snapshot_id`, `file_count`, `artifact_size_bytes` |
| ZIP upload snapshot | `local_upload.snapshot.create` | 업로드 사전 확인, ZIP 검증, 압축 해제, 파일 색인, snapshot 저장 | `upload_id`, `archive_size_bytes`, `file_count`, `rejected_reason`, `snapshot_id`, `workspace_id` |
| Ticket sync | `ticket_sync.run` | 인증 확인, page 조회, 정규화, 변경분 계산, snapshot 저장, sync 상태 갱신 | `sync_run_id`, `provider`, `workspace_id`, `external_project_id`, `page_count`, `ticket_count`, `rate_limited` |

반대로 단순 UI 문구 변경, 작은 validation 추가, 버튼 위치 변경처럼 흐름이 짧은 작업에는 Feature 전용 tracing 문서가 필요하지 않다. 기존 HTTP route span, frontend 오류 로그, 테스트 결과만으로 충분하면 `contracts/tracing/spans.md`를 만들지 않는다.

trace 속성에는 민감 값을 남기지 않는다. 원격 URL token, private key, 원본 파일 경로, 파일 내용, 외부 provider raw response는 span 속성에 넣지 않고 요약값만 남긴다.

# evidence 기준

## 표준 위치

신규 Feature는 `evidence/<feature-id>/verification.md`를 표준 evidence 문서로 쓴다. 이 문서는 완료 판단 요약, 실행한 검증, 운영자 확인 여부, 증거 링크, 실패 또는 보류 항목, 잔여 위험을 남긴다.

`quickstart.md`는 구현 전 또는 구현 중에 정하는 예정 검증 절차다. `verification.md`는 그 절차를 실제로 실행한 결과와 생략 사유를 남기는 완료 근거다. 따라서 검증 절차가 바뀌면 `quickstart.md`를 먼저 갱신하고, 실행 결과가 생기면 `verification.md`에 반영한다.

원본 로그, 스크린샷, coverage 보고서, 테스트 보고서를 repo에 전부 저장하지 않는다. 이런 대용량 또는 실행 시점 의존 자료는 CI 산출물, 테스트 보고서 저장소, release 기록에 두고, `verification.md`에는 링크와 요약만 남긴다.

## verification.md 기본 항목

`verification.md`는 원본 증거를 모두 복사하는 문서가 아니라, 완료 판단에 필요한 기준과 증거 위치를 요약하는 문서다. CI 산출물, 테스트 보고서, 빌드 출처, 필수 검사, 검토자 확인, 잔여 위험을 함께 추적하는 흐름은 GitHub, GitLab, SLSA, NIST SSDF 같은 일반적인 개발/검증 관행과도 맞는다.

`evidence/<feature-id>/verification.md`에는 최소한 다음 항목을 남긴다.

| 항목 | 의미 |
| --- | --- |
| Feature ID | 완료 판단 대상 Feature |
| 기준 commit | 검증한 코드 기준 |
| 변경 요약 | 이번 작업에서 바뀐 제품 코드와 문서 |
| 실행한 검증 | test, lint, typecheck, 수동 확인 등 실제 실행한 검증 |
| 검증 결과 | 통과, 실패, 보류 상태 |
| 운영자 확인 | 사람이 직접 확인해야 하는 절차의 수행 여부 |
| 증거 링크 | CI 로그, 테스트 보고서, 스크린샷, coverage 보고서 등 원본 증거 위치 |
| 생략한 검증 | 실행하지 않은 검증과 그 이유 |
| 잔여 위험 | 아직 남은 위험과 후속 확인 필요 사항 |
| 민감 정보 처리 | 로그, 스크린샷, 외부 응답에서 민감 값 제거 여부 |

검증 결과 상태는 다음처럼 해석한다.

| 상태 | 의미 | Gate 처리 |
| --- | --- | --- |
| 통과 | 필수 검증과 필요한 사람 확인을 끝냈고 차단 위험이 없음 | 병합 가능 |
| 보류 | 검증을 아직 실행하지 않았거나 외부 조건 때문에 완료하지 못함 | 기본적으로 병합 보류 |
| 실패 | 실행한 검증이 실패했고 원인 또는 수정 계획이 필요함 | 병합 차단 |
| 허용된 잔여 위험 | 일부 위험이 남았지만 책임자가 이유와 후속 조치를 승인함 | 승인 근거가 있을 때만 병합 가능 |

# 실행 산출물 위치

## 기본 원칙

SpecKit 산출물과 계약 기준은 제품 코드 밖에 두지만, 실행 산출물은 소유 주체가 정해진 app 또는 service 쪽에 둔다. 실행 산출물은 실제 런타임과 배포 책임을 가진 코드베이스에 있어야 한다.

아래 표는 실제 실행 파일과 그 실행 파일을 설명하거나 검증하는 기준 위치를 함께 보여준다.

| 항목 | 기준 위치 | 성격 |
| --- | --- | --- |
| DB migration | `apps/core-api/alembic/versions/` 또는 `services/<owner>/migrations/` | 실제 실행 산출물 |
| DB migration 의도 | `specs/<feature-id>/contracts/storage/migration-intent.md` | 실행 산출물의 의도와 검토 기준 |
| Feature 전용 검증용 예제 데이터 | `specs/<feature-id>/contracts/examples/` | 테스트가 참조하는 계약 기준 |
| 운영자 확인 결과 | `evidence/<feature-id>/verification.md` | 완료 판단 근거 |

## DB migration 의도 파일

Feature 전용 `storage/`는 해당 Feature가 변경하거나 의존하는 저장 경계를 설명한다. DB migration은 Feature 단위로 완전히 나누기 어렵고, 실제 실행 순서와 rollback 책임이 DB 책임자에게 묶인다. 따라서 `specs/<feature-id>/contracts/storage/`에는 실행 migration 파일이 아니라 저장 규약, 테이블 변경 의도, 하위 호환 기준, 데이터 보존 기준을 둔다.

`migration-intent.md`에는 다음 내용을 적는다.

- 변경 의도
- 추가, 변경, 제거할 table과 column
- 실제 migration 파일 위치
- backfill 또는 기본값 처리
- API와 사용처 호환성 기준
- rollback 조건과 순서
- DB 책임자 검토자

Feature는 DB 변경 이유와 검토 기준을 설명하고, DB 책임자는 실제 migration을 관리한다. Harness는 `migration-intent.md`와 실제 migration 파일이 서로 연결되어 있는지 확인한다.

# SpecKit 산출물 변경 기준

## 기본 원칙

SpecKit 산출물은 구현 중 발견한 사실에 따라 갱신할 수 있다. 단, `spec.md`, `plan.md`, `contracts/`를 바꾸는 경우에는 변경 내용과 변경 사유를 명확히 남겨야 한다. 이 산출물들은 개발자 개인의 작업 메모가 아니라 협업 기준이므로, 의미 있는 변경은 다른 산출물과 검증 기준에 미치는 영향까지 함께 확인한다.

변경 기록에는 최소한 다음 내용을 남긴다.

- 무엇이 바뀌었는가
- 왜 바뀌었는가
- 어떤 산출물이나 코드 범위에 영향을 주는가
- 어떤 검증 기준을 함께 갱신해야 하는가
- 다른 개발자 또는 다른 Feature에 영향이 있는가

## 변경 대상별 처리 기준

이 표는 파일별로 어떤 산출물을 함께 갱신해야 하는지 정한다.

| 변경 대상 | 함께 확인할 위치 |
| --- | --- |
| `spec.md` | 사용자 흐름, 성공 기준, 수용 기준, `plan.md` 영향 |
| `plan.md` | 구현 전략, 기술 선택, 위험 판단, 영향받는 task |
| `tasks.md` | 작업 순서, 병렬화 기준, 완료 상태, Feature 운영 등록부 |
| `quickstart.md` | 예정 검증 절차, 운영자 확인 절차, `verification.md` 기록 방식 |
| `contracts/` | API, event, storage, tracing, 예제 데이터 의미, 영향받는 개발자와 사용처 |
| `verification.md` | 실제 검증 결과, 증거 링크, 생략한 검증, 승인된 잔여 위험 |

## 변경 유형별 처리 기준

| 변경 유형 | 처리 기준 |
| --- | --- |
| 단순 정정 | 오타, 설명 보강, 예시 보완처럼 의미가 바뀌지 않으면 직접 수정한다 |
| 경미한 설계 보정 | 구현 순서, 내부 저장 위치, 검증 방식을 조정하면 `plan.md` 또는 `tasks.md`에 변경 사유를 기록한다 |
| 요구사항 변경 | 사용자 흐름, 성공 기준, 수용 기준이 바뀌면 `spec.md`부터 다시 맞춘다 |
| 구현 전략 변경 | 기술 선택, 작업 순서, 위험 판단이 바뀌면 `plan.md`와 `tasks.md`를 함께 맞춘다 |
| 계약 의미 변경 | 필드명, 필수 여부, 응답 구조, 이벤트 본문, 저장 규약, trace 속성, 예제 데이터 의미가 바뀌면 계약 변경 기준을 적용한다 |
| 검증 결과 변경 | 실행한 검증, 생략한 검증, 운영자 확인 결과가 바뀌면 `verification.md`를 갱신한다 |

## SpecKit 재정리 기준

SpecKit 재정리는 단순 문구 수정이 아니다. 요구사항, 구현 전략, 계약 의미, 검증 절차 중 무엇이 바뀌었는지에 따라 돌아갈 최소 단계를 정한다.

| 변경 내용 | 최소 재정리 단계 |
| --- | --- |
| 요구사항, 사용자 흐름, 성공 기준 변경 | `specify` 또는 `clarify`로 `spec.md` 갱신 → `plan.md` 영향 확인 → `tasks.md` 갱신 → `analyze` |
| 구현 전략, 기술 선택, 위험 판단 변경 | `plan.md` 갱신 → `tasks.md` 갱신 → 필요 시 `analyze` |
| 작업 순서나 병렬화 기준 변경 | `tasks.md` 갱신 → Feature 운영 등록부 갱신 |
| 계약 의미 변경 | `contracts/` 갱신 → 영향받는 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md` 확인 → 필요 시 `analyze` |
| 검증 절차 변경 | `quickstart.md` 갱신 → 실행 뒤 `verification.md` 갱신 |
| 단순 문구 정정 | 해당 문서 직접 수정 |

산출물 사이의 불일치가 의심되거나 계약 변경이 다른 개발자, 다른 Agent 작업, 다른 Feature, 공유 경계 기준에 영향을 주면 `analyze` 단계로 교차 점검한다.

# Harness와 연결

## 역할 경계

이 문서는 산출물 위치와 변경 기준을 정한다. Harness는 이 기준을 읽고 자동 검사와 PR Gate를 수행한다. 따라서 여기서는 “무엇이 어디에 있어야 하는가”를 설명하고, Harness 운영 기준에서는 “그 기준을 어떻게 검사하고 차단할 것인가”를 설명한다.

## 연결 지점

Harness와 연결되는 TCI 산출물은 다음과 같다.

| 산출물 | Harness 연결 방식 |
| --- | --- |
| `specs/<feature-id>/` | Feature 요구, 설계, 작업, 검증 절차 확인 |
| `evidence/<feature-id>/verification.md` | 완료 판단과 잔여 위험 확인 |
| `feature-registry/<feature-id>.yml` | 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역 확인 |
| `boundary-contracts/shared/` | 공유 계약 변경 시 사용처와 승인 범위 확인 |
| `docs/architecture/`, `docs/adr/` | 장기 구조 변경과 되돌리기 어려운 결정의 근거 확인 |

Harness 내부 구조, 필수 자동 검사, PR Gate 실패 처리, Feature 운영 등록부 필드 정의는 Harness 운영 기준에서 다룬다.

Gate나 검토에서 산출물 문제가 발견되면 이 문서의 기준에 맞춰 원본 산출물을 먼저 고친다. 예를 들어 evidence 누락은 `verification.md`를 보강하고, 계약 변경 누락은 `contracts/`와 영향받는 SpecKit 산출물을 갱신하며, Feature 운영 등록부의 범위 불일치는 `feature-registry/<feature-id>.yml`을 고친다.
