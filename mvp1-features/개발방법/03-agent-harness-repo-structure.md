# 용어 정의

이 문서에서 쓰는 주요 용어는 다음처럼 해석한다.

| 용어 | 의미 |
| --- | --- |
| Feature ID | `specs/`, `evidence/`, `harness/features/`를 연결하는 기능 고유 이름 |
| 완결 기능 단위 | 사용자가 체감하는 흐름 하나를 끝까지 구현하고 검증할 수 있는 작업 단위 |
| 쓰기 범위 | PR 또는 Agent가 수정해도 되는 파일 경로 목록 |
| 코드 쓰기 범위 | 제품 코드에서 수정 가능한 app, service 경로 |
| 필수 문서 범위 | Feature PR에서 영향 여부를 확인하고, 필요하면 갱신해야 하는 specs, evidence, harness 색인 경로 |
| 공동 수정 영역 | migration, lockfile, 생성물처럼 여러 작업이 동시에 건드리면 충돌 위험이 큰 경로 |
| evidence | 테스트, 운영자 확인, artifact 링크, 잔여 위험을 요약한 완료 판단 근거 |
| PR Gate | main merge 전에 CI required check와 reviewer 승인을 강제하는 장치 |
| 영향 범위 검증 | affected 검증. 바뀐 파일이 영향을 주는 app, service만 골라 검증하는 방식 |
| 사용처 검증 | consumer 검증. API, schema, event를 사용하는 쪽까지 함께 확인하는 방식 |
| 생성물 | generated output. schema나 proto 같은 원천 파일에서 자동 생성된 client, type, code |
| 기존 호환 경로 | legacy 경로. 표준으로 바꾸기 전 기존 파일명을 전환 기간 동안 읽는 fallback |
| 작업 맥락 묶음 | context bundle. Agent에게 전달할 spec, 관련 코드, 검증 기준, 주의사항 묶음 |

# 기본 구조

## Harness가 하는 일

Harness는 Feature ID를 기준으로 SpecKit 산출물, 코드 쓰기 범위, 필수 문서 범위, evidence, 민감 정보 검사, 리뷰와 PR Gate를 연결한다. 즉 중요한 것은 “같은 Feature를 어떤 기준으로 추적하고 완료 처리하는가”다. 구체적인 하위 구조와 Gate 실행 방식은 뒤의 `Harness 하위 구조` 섹션에서 설명한다.

## TCI 초기 모노레포 구조

TCI 초기 구조는 제품 코드, SpecKit 산출물, 경계 기준, evidence, Harness를 분리해서 둔다. SpecKit 기본 흐름과 충돌하지 않도록 `specs/`, `boundary-contracts/`, `docs/`, `evidence/`, `harness/`의 역할을 나눈다.

```text
tci-platform/
├─ AGENTS.md                          # repo 전체 Agent 운영 규칙
├─ apps/                              # 사용자와 직접 맞닿는 애플리케이션
│  ├─ core-api/                       # 백엔드 코어 API
│  │  └─ AGENTS.md
│  └─ web-console/                    # 프론트엔드 콘솔
│     └─ AGENTS.md
├─ services/                          # 독립 실행 성격이 강한 내부 서비스
│  ├─ analyzer/                       # 저장소 분석 엔진
│  │  └─ AGENTS.md
│  └─ workers/                        # 비동기 job 실행 영역
│     └─ AGENTS.md
├─ specs/                             # SpecKit이 만드는 feature별 산출물
│  └─ <feature-id>/                   # 하나의 완결 기능 단위
│     ├─ spec.md                      # 사용자 요구와 성공 기준
│     ├─ plan.md                      # 구현 전략과 기술 판단
│     ├─ research.md                  # 불확실한 선택지와 결정 근거
│     ├─ data-model.md                # 도메인 모델과 상태 변화
│     ├─ quickstart.md                # 사람이 따라 할 검증 절차
│     ├─ tasks.md                     # 작업 순서와 병렬화 기준
│     ├─ checklists/                  # 요구사항 품질 검사
│     └─ contracts/                   # 이 feature에 필요한 경계 기준
│        ├─ api/                      # 필요 시 feature 전용 API 초안과 schema
│        ├─ storage/                  # 필요 시 저장 규약과 migration 의도
│        ├─ tracing/                  # 필요 시 feature 전용 trace/span 기준
│        └─ examples/                 # 필요 시 feature 전용 검증용 예제 데이터
├─ boundary-contracts/                # 여러 feature가 공유하는 장기 경계 기준
│  └─ shared/                         # 공통 API, event, storage, tracing 기준
│     ├─ api/                         # 공통 API 형식, error response, auth header
│     ├─ events/                      # 공통 event envelope와 message 규칙
│     ├─ mcp/                         # 공통 Agent context bundle과 tool 입출력
│     ├─ storage/                     # 공통 저장 규약과 artifact 저장 기준
│     ├─ tracing/                     # 공통 trace/span attribute 기준
│     └─ examples/                    # 여러 feature가 함께 쓰는 검증용 예제 데이터
├─ docs/                              # feature를 넘어 유지되는 문서
│  ├─ architecture/                   # 구조 원칙과 실행 모델
│  └─ adr/                            # 핵심 의사결정 기록
├─ evidence/                          # feature 완료 판단 요약과 원본 증적 링크
│  └─ <feature-id>/                   # 검증 요약 문서와 artifact 링크
└─ harness/                           # Agent 개발 방식과 PR Gate 운영 레이어
   └─ features/                       # TCI feature 운영 인덱스
      └─ <feature-id>.yml             # specs, shared boundary-contracts, evidence, 코드 쓰기 범위, 필수 문서 범위 연결
```

제품 코드는 `apps/`와 `services/`에 두고, 기능 설명과 검증 기준은 제품 코드 밖에서 추적한다. `specs/<feature-id>/contracts/` 하위 디렉터리는 모든 Feature에 항상 만들지 않고, 해당 Feature의 경계 기준을 문서화해야 할 때만 포함한다. 여러 Feature가 함께 쓰는 장기 경계 기준은 `boundary-contracts/shared`에서 참조한다.

## 구조 원칙

### Agent 작업 범위 기준

이 구조는 Agent에게 “어디를 읽고 어디를 수정해야 하는가”를 명확히 알려주는 것을 목표로 한다. root `AGENTS.md`는 공통 운영 기준을 담고, 하위 `AGENTS.md`는 해당 영역의 기술 스택, 금지 작업, 검증 명령을 좁게 담는다.

### SpecKit 기본 경로 유지

SpecKit 산출물은 `specs/<feature-id>/`를 정식 작업 공간으로 둔다. SpecKit 경로를 그대로 쓰는 이유는 도구의 기본값을 팀 규칙의 출발점으로 삼기 위해서다. Harness는 산출물 위치를 새로 설정하기보다 SpecKit이 이미 만드는 경로를 읽고, 그 위에 팀의 검증 기준을 얹는 쪽이 안정적이다.

- SpecKit 템플릿과 명령이 `specs/<feature-id>/`를 기준으로 동작
- `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`, `tasks.md` 사이의 상대 경로와 참조 관계 유지
- Agent가 “어디를 읽어야 하는가”를 추론하지 않고 표준 경로에서 시작 가능
- Harness가 feature별 산출물을 검사할 때 경로 변환 규칙을 추가로 관리하지 않아도 됨
- SpecKit 업그레이드나 템플릿 변경 시 팀 커스텀 경로와 충돌할 가능성 감소

따라서 이 문서의 추천은 SpecKit 기본 경로를 유지하되, 여러 Feature가 공유하는 장기 경계 기준은 `boundary-contracts/shared`, 완료 판단 근거는 `evidence/`, 장기 의사결정은 `docs/adr/`로 분리한다는 뜻이다.

### Feature 기준과 공유 기준 분리

Feature 하나에서만 쓰는 경계 기준은 `specs/<feature-id>/contracts/`를 단일 기준으로 삼는다. 프론트엔드와 백엔드가 같은 기능을 병렬 개발할 때도 이 경로를 기준으로 맞춘다. SpecKit이 만든 contracts를 리뷰 중 수정해야 하면 `spec.md`, `plan.md`, `tasks.md`, `quickstart.md` 영향까지 같이 확인하고 필요한 문서를 함께 고친다.

root에는 `contracts/` 대신 `boundary-contracts/`를 둔다. 이 위치는 Feature별 복사본을 두는 곳이 아니라 여러 Feature가 공유하는 장기 기준을 두는 곳이다. 예를 들어 공통 error response, auth header, workspace id 규칙, event envelope, 공통 trace attribute, artifact 저장 규약처럼 반복 적용되는 기준만 `boundary-contracts/shared`로 올린다.

# 산출물 위치와 기준

## SpecKit 산출물 매핑

SpecKit 산출물은 `specs/<feature-id>/`에 그대로 둔다. Harness는 이 경로를 기준으로 기능 범위, 설계 결정, 작업 목록, 검증 절차를 읽는다.

| 산출물 | 권장 위치 | 역할 |
| --- | --- | --- |
| `spec.md` | `specs/<feature-id>/spec.md` | 사용자 요구와 성공 기준 |
| `plan.md` | `specs/<feature-id>/plan.md` | 구현 전략, 기술 선택, 위험 판단 |
| `research.md` | `specs/<feature-id>/research.md` | 불확실한 선택지와 결정 근거 |
| `data-model.md` | `specs/<feature-id>/data-model.md` | 도메인 모델과 상태 변화 |
| `quickstart.md` | `specs/<feature-id>/quickstart.md` | 사람이 따라 할 검증 절차 |
| `tasks.md` | `specs/<feature-id>/tasks.md` | 작업 순서와 병렬화 기준 |
| `checklists/` | `specs/<feature-id>/checklists/` | 요구사항 품질 검사 |
| `contracts/` | `specs/<feature-id>/contracts/` | 이 Feature의 단일 경계 기준 |
| `verification.md` | `evidence/<feature-id>/verification.md` | 완료 판단 요약, artifact 링크, 잔여 위험 |

## Feature 전용 tracing

Feature 전용 trace/span 기준은 `specs/<feature-id>/contracts/tracing/`에 둔다. 이 위치는 특정 Feature를 구현하고 운영할 때 어떤 작업 구간을 관찰해야 하는지 정하는 곳이다.

`specs/<feature-id>/contracts/tracing/spans.md`는 모든 Feature에 만들 필요가 없다. 이 파일은 “운영 중 장애나 지연을 추적할 때 어떤 작업 구간을 봐야 하는가”를 정하는 문서다. 단순 UI 변경, 작은 validation 추가, API field 추가처럼 흐름이 짧은 Feature에는 과하다.

`spans.md`가 필요한 경우는 다음과 같다.

- API, worker, analyzer처럼 여러 컴포넌트를 지나는 Feature
- 비동기 job이나 queue 대기가 있는 Feature
- 외부 API, Git provider, 파일 처리처럼 실패 지점이 많은 Feature
- 성능 병목이나 장애 원인 추적이 운영상 중요한 Feature
- 기존 trace로는 어느 구간이 느린지 보기 어려운 Feature

따라서 Feature 전용 `tracing/`은 필수 디렉터리가 아니라 선택 사항이다. 필요한 Feature에서만 `trace 이름`, `주요 작업 구간`, `필수 attribute`, `실패 상태 기록 방식`을 `spans.md`에 정리한다.

## evidence 문서명 호환 정책

신규 Feature는 `evidence/<feature-id>/verification.md`를 표준 문서명으로 쓴다.

Harness는 다음 순서로 evidence를 찾는다.

1. `evidence/<feature-id>/verification.md`
2. `specs/<feature-id>/delivery-evidence.md`

표준 경로와 기존 호환 경로가 둘 다 있으면 표준 경로를 우선한다. 새 PR에서 evidence를 새로 쓰거나 수정할 때는 표준 경로로 옮긴다. 기존 호환 경로는 과거 문서를 깨뜨리지 않기 위한 읽기 fallback이지, 새 Feature의 작성 위치가 아니다.

## boundary-contracts 구조

`boundary-contracts/`는 앞에서 정의한 공유 경계 기준의 예시 구조와 승격 조건을 정리하는 위치다.

### 예시 구조

예시 구조는 다음과 같다.

```text
boundary-contracts/
└─ shared/
   ├─ api/
   │  ├─ error-response.schema.yaml
   │  └─ auth-headers.md
   ├─ events/
   │  └─ event-envelope.schema.json
   ├─ mcp/
   │  └─ context-bundle.schema.json
   ├─ storage/
   │  └─ artifact-storage.md
   ├─ tracing/
   │  └─ common-attributes.md
   └─ examples/
      └─ workspace-error.response.json
```

### 하위 디렉터리 역할

각 하위 디렉터리 역할은 다음과 같다.

- `api/`: 공통 error response, auth header, pagination 같은 API 공통 기준
- `events/`: 여러 worker와 analyzer가 함께 쓰는 event envelope와 message 규칙
- `mcp/`: 외부 Agent에게 공통으로 제공할 context bundle과 tool 입출력 기준
- `storage/`: artifact 저장 위치, 보존 기간, 호환성 같은 공통 저장 기준
- `tracing/`: 여러 Feature가 공유하는 trace attribute와 naming 기준
- `examples/`: 여러 Feature가 함께 쓰는 공통 검증용 예제 데이터

공유 경계 기준은 구현 전에 고정하고, 구현 뒤에는 테스트와 evidence가 같은 기준을 검증했는지 확인한다.

### 공유 기준 승격 기준

Feature contracts를 `boundary-contracts/shared`로 승격하는 기준은 다음과 같다.

| 기준 | 의미 |
| --- | --- |
| 반복 사용 | 두 개 이상의 Feature가 같은 API 형식, event envelope, trace attribute를 사용 |
| Feature와 독립된 의미 | 특정 Feature의 세부 요구가 아니라 제품 전체에서 같은 의미로 쓰임 |
| 장기 유지 필요 | 한 번 정하면 여러 release 동안 유지해야 하는 기준 |
| 공유 필요 확정 | 두 번째 사용처가 생겼거나 승인된 Feature 계획에서 같은 기준을 재사용하기로 확정됨 |
| 공통 언어 역할 | 팀이 같은 error 형식, event 형식, trace attribute 이름으로 대화해야 함 |

## docs 구조

`docs/`는 장기 구조 설명과 의사결정 기록의 위치다. SpecKit 산출물은 `specs/`에 두고, `docs/`에는 feature를 넘어서 계속 유지해야 하는 내용을 둔다.

```text
docs/
├─ architecture/                       # 제품 전체 구조와 실행 모델
│  ├─ run-task-model.md                # run, task, job의 생명주기와 상태 전이
│  ├─ worker-boundary.md               # core-api, worker, analyzer 책임 경계
│  ├─ storage-model.md                 # DB, artifact, snapshot 저장 모델
│  ├─ security-boundary.md             # 인증 정보, 민감 정보, 외부 입력 처리 원칙
│  └─ observability-model.md           # 로그, metric, trace 운영 기준
└─ adr/                                # 되돌리기 어려운 결정 기록
   ├─ 0001-monorepo-agent-harness.md   # 초기 모노레포와 Harness 채택 결정
   ├─ 0002-storage-ownership.md        # DB migration과 storage owner 결정
   └─ 0003-agent-gate-policy.md        # Agent PR Gate와 evidence 정책 결정
```

`docs/architecture/`는 특정 Feature 하나에 종속되지 않는 구조 문서를 둔다. 예를 들어 task 상태 전이, worker 책임 경계, 저장소 snapshot 보관 방식, 민감 정보 처리 원칙처럼 여러 Feature가 반복해서 따라야 하는 기준이다.

`docs/adr/`는 팀이 되돌리기 어려운 결정을 왜 했는지 남기는 위치다. ADR은 “무엇을 선택했는가”보다 “왜 이 선택을 했고, 어떤 대안을 포기했는가”를 남긴다. 나중에 구조를 바꾸거나 주요 운영 기준을 수정할 때 판단 근거가 된다.

따라서 Feature 구현 중 생기는 세부 요구, 작업 목록, 검증 절차는 `specs/<feature-id>/`에 둔다. 여러 Feature에 반복 적용될 구조 원칙이나 되돌리기 어려운 결정만 `docs/`로 올린다.

## evidence 구조

`evidence/`는 Feature 완료 판단 요약을 남기는 위치다. 업계에서 자주 쓰는 CI artifact, test report, coverage report, PR checklist 흐름에 맞춰 repo에는 요약과 링크만 둔다.

```text
evidence/
└─ repository-snapshot-detail/
   └─ verification.md
```

evidence를 `specs/<feature-id>/` 안에 넣을 수도 있지만, 별도 디렉터리로 두는 편이 Harness 검사와 CI Gate 연결에 유리하다. 문서 작성 흐름은 `specs/`, 완료 판정은 `evidence/`로 분리된다.

`verification.md`에는 검증한 commit, 실행한 test/lint/typecheck, 운영자 확인 여부, CI artifact 링크, 실패 또는 보류 항목, 잔여 위험을 적는다. 원본 로그, 스크린샷, coverage report, test report를 repo에 전부 저장하지 않는다. 이런 대용량 또는 실행 시점 의존 자료는 CI artifact, test report 저장소, release 기록에 두고, `verification.md`에는 링크와 요약만 남긴다.

## 실행 산출물 위치

SpecKit 산출물과 경계 기준은 제품 코드 밖에 두지만, 실행 산출물은 owner가 있는 app/service 쪽에 둔다.

| 실행 산출물 | 권장 위치 | 보완 문서 |
| --- | --- | --- |
| DB migration | `apps/core-api/alembic/versions/` 또는 `services/<owner>/migrations/` | `specs/<feature-id>/contracts/storage/migration-intent.md` |
| Feature 전용 검증용 예제 데이터 | `specs/<feature-id>/contracts/examples/` | app/service test가 같은 예제를 참조 |
| 운영자 확인 결과 | `evidence/<feature-id>/verification.md` | 실행 일시, commit, 환경, 실패 조건 요약 |

### DB Migration 의도 파일

DB migration은 Feature 단위로 완전히 나누기 어렵고, 실제 실행 순서와 rollback 책임이 DB owner에게 묶인다. 따라서 `specs/<feature-id>/contracts/storage/`에는 실행 migration 파일이 아니라 저장 규약, 테이블 변경 의도, backward compatibility, 데이터 보존 기준을 둔다.

`migration-intent.md`에는 다음 내용을 적는다.

- 변경 의도
- 추가, 변경, 제거할 table과 column
- 실제 migration 파일 위치
- backfill 또는 기본값 처리
- API와 사용처 호환성 기준
- rollback 조건과 순서
- DB owner reviewer

즉 Feature는 DB 변경 이유와 검토 기준을 설명하고, DB owner는 실제 migration을 관리한다. Harness는 `migration-intent.md`와 실제 migration 파일이 서로 연결되어 있는지 확인한다.

# Harness 하위 구조

`harness/`는 제품 코드가 아니라 Agent 개발 방식과 PR Gate를 운영하는 레이어다. 아래 구조는 이 레이어를 규칙, 형식, 검사, 설정으로 나누는 예시다.

## 디렉터리 구성

### 권장 구조

권장 구조는 다음과 같다.

```text
harness/
├─ README.md
├─ features/  # TCI 운영 인덱스
│  └─ repository-snapshot-detail.yml
├─ rules/
│  ├─ feature-id.md
│  ├─ evidence.md
│  ├─ review-finding.md
│  ├─ sensitive-data.md
│  ├─ context-bundle.md
│  └─ repo-boundary.md
├─ schemas/
│  ├─ evidence.schema.json
│  ├─ task-status.schema.json
│  ├─ review-finding.schema.json
│  ├─ context-bundle.schema.json
│  └─ feature-record.schema.json
├─ templates/
│  ├─ context-bundle.md
│  ├─ evidence.md
│  ├─ pr-description.md
│  └─ reviewer-checklist.md
├─ scripts/
│  ├─ check-feature-id
│  ├─ check-evidence
│  ├─ check-sensitive-data
│  ├─ check-write-scope
│  ├─ check-review-findings
│  └─ check-affected
├─ config/
│  ├─ harness.yml
│  ├─ ownership.yml
│  ├─ gates.yml
│  └─ allowed-tools.yml
└─ examples/
   ├─ evidence.example.md
   ├─ context-bundle.example.md
   └─ feature-record.example.yml
```

### 디렉터리 역할

각 디렉터리의 역할은 다음과 같다.

- `features/`: Feature ID별 specs, boundary-contracts, evidence, 코드 쓰기 범위, 필수 문서 범위를 연결하는 TCI 운영 인덱스
- `rules/`: 사람이 읽는 정책, script가 따라야 할 기준, Agent instruction 원천
- `schemas/`: evidence, task status, review finding, context bundle의 구조화된 형식
- `templates/`: PR 본문, evidence, reviewer checklist를 같은 형식으로 작성하게 하는 양식
- `scripts/`: CI와 PR Gate에서 실행하는 자동 검사 명령
- `config/`: 공동 수정 영역, required check, reviewer Gate, 허용 MCP와 tool 범위를 담는 팀 정책
- `examples/`: 좋은 산출물 예시와 Agent prompt에 넣기 좋은 기준 샘플

### Gate 실행 흐름

관계는 다음과 같다.

```text
rules/evidence.md              # 기준 설명
    ↓
templates/evidence.md          # 작성 양식
    ↓
schemas/evidence.schema.json   # 구조 검증
    ↓
scripts/check-evidence         # CI 자동 검사
    ↓
required check                 # main merge 차단
```

예를 들어 `rules/evidence.md`가 evidence 문서에 commit, checks, artifact link, residual risk가 있어야 한다고 정한다. `scripts/check-evidence`는 PR에서 표준 evidence 또는 허용된 기존 호환 evidence가 있는지, 필수 항목이 채워졌는지 확인한다. 누락되면 `exit 1`을 내고 CI가 실패한다. reviewer는 script가 판단하기 어려운 맥락, 예를 들어 잔여 위험이 실제로 허용 가능한지 같은 부분을 확인한다.

## features/feature-id.yml

`harness/features/<feature-id>.yml`은 TCI 운영 인덱스다. Harness가 이 파일을 읽으면 feature별로 어떤 산출물, 구현 범위, 경계 기준, evidence를 검사해야 하는지 알 수 있다.

### 예시

```yaml
feature_id: repository-snapshot-detail
specs_path: specs/repository-snapshot-detail
feature_contracts_path: specs/repository-snapshot-detail/contracts
shared_boundary_contracts_path: boundary-contracts/shared
evidence_path: evidence/repository-snapshot-detail
code_write_scope:
  - apps/core-api/**
  - apps/web-console/**
required_document_scope:
  - specs/repository-snapshot-detail/**
  - evidence/repository-snapshot-detail/**
  - harness/features/repository-snapshot-detail.yml
shared_areas:
  - apps/core-api/alembic/versions/**
  - apps/web-console/src/generated/**
required_checks:
  - check-evidence
  - check-sensitive-data
  - check-write-scope
```

### 필드 정의

`harness/features/<feature-id>.yml`의 필드는 다음처럼 정의한다.

| 필드 | 필수 여부 | 의미 |
| --- | --- | --- |
| `feature_id` | 필수 | `specs/`, `evidence/`, PR 본문에서 같은 이름으로 추적할 Feature ID |
| `specs_path` | 필수 | SpecKit 산출물이 있는 경로 |
| `feature_contracts_path` | 필수 | 이 Feature의 단일 경계 기준 경로 |
| `shared_boundary_contracts_path` | 선택 | 이 Feature가 참조하는 공통 경계 기준 경로 |
| `evidence_path` | 필수 | 표준 evidence 경로 |
| `code_write_scope` | 필수 | PR 또는 Agent가 수정할 수 있는 제품 코드 경로 |
| `required_document_scope` | 필수 | Feature PR에서 영향 여부를 확인해야 하는 specs, evidence, harness 색인 경로. 영향이 있으면 갱신하고, 영향이 없으면 PR 본문이나 evidence에 생략 근거를 남김 |
| `shared_areas` | 선택 | lockfile, migration, 생성물처럼 충돌 위험이 큰 공동 수정 영역 |
| `required_checks` | 필수 | main merge 전에 통과해야 하는 Harness 검사 |
| `owners` | 선택 | 작업 책임 owner 또는 team |
| `reviewers` | 선택 | 필수 reviewer 또는 reviewer group |
| `risk_gates` | 선택 | 보안, 민감 정보, 외부 입력, 운영자 확인 같은 추가 Gate |

### Gate 실행 기준

Harness Gate의 실행 기준은 다음처럼 둔다.

| 검사 | 입력 | 실패 조건 | required check 이름 | reviewer 확인 |
| --- | --- | --- | --- | --- |
| `check-feature-id` | PR 제목과 본문, `harness/features/<feature-id>.yml`, `specs/<feature-id>/` | Feature ID가 없거나 경로가 서로 맞지 않음 | `harness / check-feature-id` | PR 범위가 하나의 Feature로 설명되는지 확인 |
| `check-evidence` | `evidence/<feature-id>/verification.md` | 표준 evidence가 없거나 필수 항목이 비어 있음 | `harness / check-evidence` | 잔여 위험과 보류 항목이 허용 가능한지 확인 |
| `check-sensitive-data` | diff, evidence 요약, PR 본문, artifact 링크 | token, cookie, private key, DB URL, 원본 secret 값 포함 | `harness / check-sensitive-data` | 민감 값이 제거된 요약만 남았는지 확인 |
| `check-write-scope` | `git diff`, `code_write_scope`, `required_document_scope`, `shared_areas` | 허용되지 않은 경로를 수정하거나, 문서 영향 판단이 없거나, 필요한 문서 갱신이 빠지거나, 공동 수정 영역 승인이 없음 | `harness / check-write-scope` | 범위 확장이 필요한지 확인 |
| `check-affected` | 변경 파일, 의존 관계 그래프, 실행된 검증 | 영향받은 app/service 검증이 빠짐 | `harness / check-affected` | 생략한 검증의 이유가 타당한지 확인 |

GitHub에서는 이 check를 branch protection의 required status check로 걸고, GitLab에서는 protected branch의 required pipeline job으로 건다. script는 실패 조건을 기계적으로 판단하고, reviewer는 맥락 판단이 필요한 항목을 확인한다.

## 초기 MVP 하네스 구조

초기 MVP에서는 모든 구조를 한 번에 만들 필요가 없다. CI와 PR Gate로 연결할 최소 구조는 다음 정도면 충분하다.

```text
harness/
├─ README.md
├─ features/
│  └─ <feature-id>.yml
├─ rules/
│  ├─ evidence.md
│  ├─ sensitive-data.md
│  └─ repo-boundary.md
├─ templates/
│  ├─ evidence.md
│  └─ pr-description.md
├─ scripts/
│  ├─ check-evidence
│  ├─ check-sensitive-data
│  └─ check-feature-id
└─ config/
   └─ harness.yml
```

이 최소 구조로 먼저 Feature 색인, evidence 형식, 민감 정보 검사를 고정한다. MVP 단계에서는 별도 `schemas/` 없이 `rules/`와 `templates/`에 적힌 필수 항목을 `scripts/`가 직접 검사해도 된다. 단, script가 검사하는 필수 항목은 해당 `rules/` 문서에 먼저 명시해야 한다. 이후 Feature가 늘어나고 같은 형식이 반복되면 `schemas/`, `examples/`, `check-write-scope`, `check-review-findings`를 추가한다.

# 운영 기준

## 민감 정보 처리 기준

Harness는 Agent와 CI가 읽는 입력에서 민감 정보가 새지 않도록 기준을 둔다. 민감 정보 처리는 보안팀만 보는 별도 절차가 아니라 PR Gate의 기본 검사여야 한다.

`docs/architecture/security-boundary.md`는 제품 전체의 보안 원칙을 설명하는 장기 문서다. `harness/rules/sensitive-data.md`는 그 원칙을 PR Gate에서 어떻게 검사할지 정하는 실행 규칙이다.

| 대상 | 기준 |
| --- | --- |
| token, cookie, private key, password, DB URL | repo, evidence, PR 본문, MCP 입력, Agent 입력에 원본 값을 남기지 않음 |
| `.env`, auth file, provider credential | 값은 읽거나 전달하지 않고 키 이름, provider 종류, 존재 여부 같은 metadata만 사용 |
| provider 원본 응답과 실행 로그 | 필요한 상태, 에러 코드, 요청 ID만 요약하고 민감 값은 제거 |
| 외부 issue, 웹 문서, 사용자 입력 | prompt injection 가능 입력으로 보고 Agent에게 필요한 최소 범위만 전달 |
| CI artifact 링크 | 접근 권한이 제한된 위치에 두고, 링크된 원본 로그에 민감 값이 없는지 확인 |
| evidence 요약 | 민감 값 대신 환경, commit, 검증 명령, 결과, 잔여 위험만 기록 |

`check-sensitive-data`는 자동으로 찾을 수 있는 패턴을 막고, reviewer는 자동 검사가 놓칠 수 있는 맥락을 본다. 예를 들어 외부 provider 응답의 raw body를 evidence에 붙이는 대신 “GitHub API 403, scope 부족, request id 기록”처럼 요약한다.

## 모노레포 운영에 필요한 장치

TCI가 모노레포를 채택한다는 것은 폴더를 한 저장소에 모으는 것만을 뜻하지 않는다. 여러 개발자와 Agent가 같은 repo에서 병렬 작업해도 main branch가 깨지지 않게 하는 운영 장치가 필요하다.

- app, service, boundary 의존 관계 그래프
- 변경 파일 기준 영향 범위 build, lint, typecheck, test 실행
- local 또는 remote cache 정책
- CODEOWNERS 또는 경로별 reviewer Gate
- 공통 schema와 공통 타입 변경 시 사용처 검증
- lockfile, migration, 생성 파일 단일 작업 소유권
- secret scan, dependency audit, evidence Gate의 required check 연결

각 항목은 다음처럼 해석한다.

| 조건 | 의미 | 예시 |
| --- | --- | --- |
| 의존 관계 그래프 | 변경 영향 계산용 app, service 관계 | `web-console -> specs/<feature-id>/contracts/api` |
| 영향 범위 검증 | 영향받은 영역만 build, lint, typecheck, test 실행 | 공통 타입 변경 시 API와 UI typecheck |
| cache 정책 | 같은 입력의 검증 결과 재사용 | source, lockfile, env key가 같으면 결과 재사용 |
| CODEOWNERS | 경로별 필수 reviewer 지정 | `apps/core-api/** @backend-team` |
| 사용처 검증 | 공유 schema 사용자까지 확인 | API schema 변경 시 UI 예제 데이터 검증 |
| 단일 작업 소유권 | 충돌 파일 동시 수정 방지 | lockfile, migration, 생성된 API client |
| secret scan | 인증 정보 커밋 방지 | token, private key, DB URL |
| dependency audit | 의존성 취약점 확인 | `pnpm audit`, `pip-audit` |
| evidence Gate | 검증 요약 없으면 merge 차단 | `evidence/<feature-id>/verification.md` |

이 조건이 없으면 모노레포는 Agent에게 편한 구조가 아니라 unrelated diff, 전체 CI, 경계 없는 공유 코드가 누적되는 구조가 된다.

# 결론

TCI는 초기 개발 구조를 모노레포로 둔다. 단, 모노레포를 모든 파일을 자유롭게 수정하는 구조로 쓰지 않고, Feature ID, 쓰기 범위, evidence, PR Gate로 병렬 작업을 통제한다.
