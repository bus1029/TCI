# SpecKit 기반 TCI 프로젝트 운영 절차

## 문서 목적

이 문서는 SpecKit 기반 TCI 프로젝트에서 Feature 산출물을 어떤 순서로 만들고, 변경하고, 완료 근거까지 연결하는지 정리한다.

이 문서에서 쓰는 주요 용어는 다음처럼 해석한다.

| 용어 | 의미 |
| --- | --- |
| Feature ID | `specs/`, `evidence/`, `feature-registry/`를 연결하는 기능 고유 이름 |
| Feature 등록부 | Feature별 산출물 경로, 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토와 검사 조건을 연결하는 `feature-registry/<feature-id>.yml` |
| 검증 절차 | 구현자가 실행하거나 운영자가 따라 할 예정 검증 기준. 기본 위치는 `specs/<feature-id>/quickstart.md` |
| 완료 근거 | 실제로 실행한 검증, 생략 사유, 승인된 잔여 위험을 남긴 기록. 기본 위치는 `evidence/<feature-id>/verification.md` |
| PR Gate | main 병합 전에 산출물 누락, 범위 위반, 민감 정보 노출, 검토 누락을 확인하는 자동 검사와 검토 흐름 |
| Harness | Feature 등록부와 산출물을 읽고 PR Gate를 실행하는 운영 레이어 |

## 문서 범위

이 문서의 결정 범위는 다음과 같다.

- Feature 산출물 생성 흐름
- Feature 등록부 생명주기와 상태 기준
- 공유 계약 승격과 계약 변경 처리
- tracing 기준 작성 여부
- 완료 근거 작성과 검증 결과 상태
- SpecKit 산출물 변경과 재정리 기준
- Harness 연결 지점과 범위 위반 처리 기준

이 문서가 정하지 않는 것은 다음과 같다.

- 산출물의 표준 위치와 디렉터리 구조
- Harness 내부 디렉터리 구조와 검사 구현 방식
- Feature 등록부의 전체 필드 schema
- 개별 Feature의 상세 요구사항
- 앱, 서비스 내부 코드 작성 규칙
- 테스트 프레임워크별 작성 방식
- CI 구현 방식

## 전체 운영 절차

### 기본 흐름

Feature 산출물은 보통 다음 순서로 생긴다.

1. Feature ID를 정하고 `feature-registry/<feature-id>.yml` 초안을 만든다
2. SpecKit으로 `specs/<feature-id>/` 산출물을 만든다
3. API, 이벤트, 저장 경계, 관측 기준 같은 협업 경계가 필요하면 `specs/<feature-id>/contracts/`에 Feature 전용 계약을 둔다
4. 구현 전 `quickstart.md`에 예정 검증 절차를 정리한다
5. 구현 중 범위나 계약 의미가 바뀌면 `contracts/`를 원본 기준으로 고치고 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md`, Feature 등록부 영향을 함께 확인한다
6. 구현 중에는 `evidence/<feature-id>/verification.md` 초안을 만들 수 있고, PR 준비나 완료 판단 직전에는 실제 검증 결과와 잔여 위험을 확정한다
7. PR Gate는 Feature 등록부와 산출물을 읽어 누락과 범위 위반을 확인한다

### 주요 산출물

| 산출물 | 운영상 역할 |
| --- | --- |
| `specs/<feature-id>/` | 요구사항, 설계, 작업 목록, 예정 검증 절차의 기준 |
| `specs/<feature-id>/contracts/` | Feature 전용 협업 경계 기준 |
| `evidence/<feature-id>/verification.md` | 실제 검증 결과와 완료 판단 근거 |
| `feature-registry/<feature-id>.yml` | 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토와 검사 조건 연결 |
| `boundary-contracts/` | 여러 Feature가 공유하는 장기 경계 기준 |
| `docs/architecture/`, `docs/adr/` | Feature를 넘어 유지되는 구조와 결정 근거 |

## Feature 등록부 운영

### 생명주기

Feature 등록부는 한 번에 완성되는 파일이 아니다. Feature 접수 시 초안을 만들고, `plan.md`와 `tasks.md`가 안정되면 구현 가능한 상태로 갱신하며, PR 전에는 실제 변경 범위와 완료 근거를 기준으로 다시 맞춘다. 이 문서에서는 등록부가 연결해야 할 산출물과 변경 기준만 다루고, 전체 schema와 세부 검사 규칙은 Harness 운영 기준에서 다룬다.

기본 필드는 Feature 등록부 기준과 맞춘다.

```yaml
feature_id: 004-zip-upload-workspace-delete
specs_path: specs/004-zip-upload-workspace-delete
evidence_path: evidence/004-zip-upload-workspace-delete
code_write_scope:
  - apps/core-api/**
required_document_scope:
  - specs/004-zip-upload-workspace-delete/**
  - evidence/004-zip-upload-workspace-delete/**
  - feature-registry/004-zip-upload-workspace-delete.yml
shared_areas:
  - apps/core-api/alembic/versions/**
review_owners:
  - backend-team
required_reviews:
  - owner-approval
  - shared-area-approval
required_checks:
  - check-feature-id
  - check-evidence
  - check-sensitive-data
  - check-write-scope
```

### 기본 필드

주요 필드는 다음처럼 해석한다.

| 필드 | 의미 |
| --- | --- |
| `feature_id` | `specs/`, `evidence/`, `feature-registry/`를 연결하는 Feature ID |
| `specs_path` | Feature의 SpecKit 산출물 위치 |
| `evidence_path` | Feature의 완료 근거 위치 |
| `code_write_scope` | 제품 코드에서 수정할 수 있는 경로 |
| `required_document_scope` | 영향 여부를 확인하고 필요하면 갱신해야 하는 문서 경로 |
| `shared_areas` | 충돌 위험 때문에 별도 승인이 필요한 공동 수정 영역 |
| `review_owners` | 변경 내용을 확인할 책임 팀 또는 책임자 |
| `required_reviews` | PR Gate 전에 필요한 검토 또는 승인 조건 |
| `required_checks` | PR 전에 통과해야 하는 자동 검사 |

### 상태 기준

| 상태 | 시점 | 필수 정보 | 검사에 쓰이는 기준 |
| --- | --- | --- | --- |
| `draft` | Feature ID를 정하고 작업을 접수한 직후 | `feature_id`, 만들 예정인 `specs_path`, `evidence_path` | 완료 조건으로 쓰지 않고 추적 시작점으로만 사용 |
| `implementation-ready` | `plan.md`와 `tasks.md`로 구현 범위가 정리된 뒤 | `code_write_scope`, `required_document_scope`, `shared_areas`, `review_owners`, `required_reviews`, `required_checks` | 구현 중 범위 이탈과 문서 누락을 확인하는 기준 |
| `completion-check` | PR 준비 또는 완료 판단 직전 | 실제 수정 범위와 갱신 문서를 반영한 `code_write_scope`, `required_document_scope`, `shared_areas`, `required_reviews`, `required_checks` | PR Gate에서 누락, 범위 위반, 검토 누락을 확인할 때 쓰는 기준 |

`completion-check`에서는 `evidence_path` 아래의 `verification.md`가 필수 완료 근거가 된다. 실제 실행한 검증, 생략한 검증, 공동 수정 영역 승인 근거, 잔여 위험은 `verification.md`와 PR 본문에 남긴다.

필수 검토자는 `review_owners`와 `required_reviews`에 선언한다. 검토 결과와 승인 근거는 `verification.md`와 PR 검토 기록에 남긴다.

## 계약 운영 기준

### 공유 계약 승격 기준

Feature 전용 계약은 다음 조건을 만족할 때 `boundary-contracts/`로 승격한다.

| 기준 | 의미 |
| --- | --- |
| 반복 사용 | 두 개 이상의 Feature가 같은 API 형식, 이벤트 공통 구조, trace 속성을 사용 |
| Feature와 독립된 의미 | 특정 Feature의 세부 요구가 아니라 제품 전체에서 같은 의미로 쓰임 |
| 장기 유지 필요 | 한 번 정하면 여러 릴리스 동안 유지해야 하는 기준 |
| 공유 필요 확정 | 두 번째 사용처가 생겼거나 승인된 Feature 계획에서 같은 기준을 재사용하기로 확정됨 |
| 공통 언어 역할 | 팀이 같은 오류 형식, 이벤트 형식, trace 속성 이름으로 대화해야 함 |

공유 계약은 가능한 한 구현 전에 고정한다. 다만 실제 구현 중 두 번째 사용처가 확인되거나, 구현 뒤에 같은 기준을 반복 적용해야 한다는 사실이 드러날 수 있다. 이 경우에도 공유 계약으로 승격하기 전에는 영향 범위와 검증 기준을 먼저 정리해야 한다.

| 발견 시점 | 처리 기준 | 완료 조건 미충족 기준 |
| --- | --- | --- |
| 구현 전 | `boundary-contracts/`에 공유 기준을 먼저 만들고 Feature 전용 계약은 참조만 남김 | 공유 기준 책임자와 사용처 검토가 없으면 산출물 기준 미충족 |
| 구현 중 | 현재 Feature의 계약을 임시 기준으로 고정한 뒤, 두 번째 사용처와 함께 공유 계약 승격 여부를 결정 | 기존 구현과 새 사용처가 서로 다른 의미로 같은 이름을 쓰면 계약 기준 미충족 |
| 구현 후 | 반복 사용이 확인된 시점에 공유 계약으로 승격하고, 기존 Feature에는 공유 기준 참조와 재검증 기록을 추가 | 승격 후 검증 기준 갱신 기록이 없으면 완료 근거 미충족 |

Feature 전용 계약을 공유 계약으로 승격할 때는 다음 순서로 정리한다.

1. `boundary-contracts/`에 공유 기준을 만들거나 기존 기준을 갱신한다
2. 기존 Feature 전용 계약에는 공유 기준 참조 또는 차이점만 남긴다
3. 영향받는 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md` 기준을 확인한다
4. 다른 Feature가 같은 계약을 참조하면 사용처 검증 범위를 함께 정리한다
5. 공유 계약 책임자 또는 책임 검토자의 승인 조건을 남긴다

예를 들어 첫 Feature에서만 쓰던 `specs/<feature-id>/contracts/events.md`의 이벤트 envelope가 두 번째 Feature에서도 같은 의미로 필요해지면, 공통 구조는 `boundary-contracts/events/event-envelope.md`로 올리고 기존 Feature 계약에는 해당 공유 기준 참조와 Feature별 차이점만 남긴다.

승격 조건을 만족하지 못하면 공유 계약으로 올리지 않는다. 두 번째 사용처가 확정되지 않았거나 책임자가 정해지지 않았으면 Feature 전용 계약으로 유지하고, 기존 공유 계약과 의미가 충돌하면 이름과 의미를 정리할 때까지 완료 조건 미충족으로 남긴다. 승격을 보류한 이유와 재검토 조건은 해당 Feature의 `plan.md`나 `verification.md`에 남긴다.

구현 후 공유 계약으로 승격하더라도 기존 `verification.md`의 과거 완료 근거를 덮어쓰지 않는다. 새 승격 작업의 기준 commit, 변경 요약, 재검증 결과를 현재 변경의 완료 근거로 남기고, 기존 Feature의 과거 기록에는 필요하면 공유 계약 참조가 갱신되었음을 추가한다.

### 계약 변경 처리

`contracts/` 변경은 협업 경계 변경으로 취급한다. 계약은 개발자 개인의 구현 세부사항이 아니라 프론트엔드, 백엔드, worker, analyzer, 테스트와 완료 근거 기록이 맞춰야 하는 기준이다. 따라서 계약 의미가 바뀌면 단순 문서 수정으로 처리하지 않는다.

계약 의미 변경에 해당하는 예시는 다음과 같다.

- API 요청 또는 응답 필드 추가, 제거, 이름 변경
- 필수 필드와 선택 필드 기준 변경
- 오류 응답 형식 변경
- 이벤트 본문 구조 변경
- DB 테이블, 컬럼, 상태 전이 의미 변경
- trace/span 이름 또는 필수 속성 변경
- 검증용 예시 데이터의 의미 변경

계약 의미가 바뀌면 먼저 `contracts/` 또는 `boundary-contracts/`의 기준 문서를 고친다. 그다음 영향받는 `plan.md`, `tasks.md`, `quickstart.md`, 이미 실행된 `verification.md`, Feature 등록부를 확인한다. 다른 개발자나 다른 Feature가 참조하는 계약이면 계약 변경 제안, 영향 범위 확인, 관련 작업 재분해, PR 준비와 검토 흐름으로 처리한다. PR Gate에서 이 상태를 어떻게 표시할지는 Harness 운영 기준에서 다루지만, 이 문서는 어떤 산출물을 고쳐야 하는지까지 정한다.

계약 변경 기록은 변경된 계약 문서에 남기고, PR 준비 시 `verification.md`에 요약한다. 공유 계약 변경처럼 영향 범위가 넓으면 PR 본문에도 사용처, 검토자, 승인 상태를 남긴다.

다음 변경은 자동 검사만으로 완료 처리하지 않고 사람 검토를 함께 요구한다.

| 변경 | 필요한 검토 | 기록 위치 |
| --- | --- | --- |
| 공유 계약 추가, 변경, 승격 | 계약 책임자 또는 영향받는 사용처 책임자 검토 | 계약 문서, `verification.md`, PR 검토 |
| DB migration 의도 변경 | DB 책임자 검토와 실제 migration 파일 위치 확인 | `storage-migration-intent.md`, `verification.md`, PR 검토 |
| 보안 경계 변경 | 보안 또는 아키텍처 책임자 검토 | `verification.md`, PR 검토 |
| 운영자 직접 확인 절차 변경 | 실제 수행자 또는 운영 책임자 확인 | `quickstart.md`, `verification.md` |
| 잔여 위험을 남긴 완료 판단 | Feature 책임자의 명시 승인 | `verification.md`, PR 검토 |

## Tracing 기준

### Feature 전용 tracing

Feature 전용 trace/span 기준은 `specs/<feature-id>/contracts/tracing-spans.md`에 둔다. 이 파일은 특정 Feature를 구현하고 운영할 때 어떤 작업 구간을 관찰해야 하는지 정하는 곳이다. OTel 설정 자체를 Feature마다 다르게 만든다는 뜻이 아니라, 같은 OTel 기반 위에서 어떤 작업 구간을 나눠 볼지 Feature별로 정한다는 뜻이다.

trace는 하나의 요청이나 작업 흐름 전체다. span은 그 흐름 안의 한 작업 구간이다. 예를 들어 “저장소 snapshot 생성”이라는 trace 안에는 “연결 정보 확인”, “원격 저장소 fetch”, “파일 tree 분석”, “산출물 저장”, “DB 기록” 같은 span이 들어갈 수 있다. 장애나 지연이 생겼을 때 span을 보면 어느 구간에서 문제가 생겼는지 좁힐 수 있다.

**작성 대상**

`specs/<feature-id>/contracts/tracing-spans.md`는 모든 Feature에 만들 필요가 없다. 이 파일은 운영 중 장애나 지연을 추적할 때 어떤 작업 구간을 봐야 하는지 정하는 문서다.

`tracing-spans.md`가 필요한 경우는 다음과 같다.

- API, worker, analyzer처럼 여러 컴포넌트를 지나는 Feature
- 비동기 job이나 queue 대기가 있는 Feature
- 외부 API, Git provider, 파일 처리처럼 실패 지점이 많은 Feature
- 성능 병목이나 장애 원인 추적이 운영상 중요한 Feature
- 기존 trace로는 어느 구간이 느린지 보기 어려운 Feature

필요한 Feature에서만 trace 이름, 주요 작업 구간, 필수 속성, 실패 상태 기록 방식을 정리한다.

**예시**

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

**만들지 않는 경우**

단순 UI 문구 변경, 작은 입력 검증 추가, 버튼 위치 변경처럼 흐름이 짧은 작업에는 Feature 전용 tracing 문서가 필요하지 않다. 기존 HTTP route span, 프론트엔드 오류 로그, 테스트 결과만으로 충분하면 `contracts/tracing-spans.md`를 만들지 않는다.

**민감 정보**

trace 속성에는 민감 값을 남기지 않는다. 원격 URL token, private key, 원본 파일 경로, 파일 내용, 외부 provider 원본 응답은 span 속성에 넣지 않고 요약값만 남긴다.

## 완료 근거 기준

### 표준 위치

신규 Feature는 `evidence/<feature-id>/verification.md`를 표준 완료 근거 문서로 쓴다. 이 문서는 완료 판단 요약, 실행한 검증, 운영자 확인 여부, 증거 링크, 실패 또는 보류 항목, 잔여 위험을 남긴다.

`quickstart.md`는 구현 전 또는 구현 중에 정하는 예정 검증 절차다. `verification.md`는 그 절차를 실제로 실행한 결과와 생략 사유를 남기는 완료 근거다. 구현 중에는 `verification.md` 초안을 만들 수 있지만, 이때는 검증 결과를 `보류`로 둔다. `completion-check` 시점에는 기준 commit, 실행 결과, 생략 사유, 사람 확인 여부, 승인된 잔여 위험을 확정해야 한다.

원본 로그, 스크린샷, coverage 보고서, 테스트 보고서를 repo에 전부 저장하지 않는다. 이런 대용량 또는 실행 시점 의존 자료는 CI 산출물, 테스트 보고서 저장소, 릴리스 기록에 두고, `verification.md`에는 링크와 요약만 남긴다.

증거 링크는 다음처럼 추적 가능한 위치를 남긴다.

- CI run URL 또는 artifact URL
- 테스트 보고서 저장소의 report URL
- 릴리스 기록이나 배포 기록 URL

토큰이 포함된 URL, 로컬 개인 경로, 민감 값이 보이는 스크린샷 원본은 증거 링크로 남기지 않는다.

### verification.md 기본 항목

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

검증 결과 상태는 다음처럼 해석한다. 이 표는 완료 판단 기준을 정하고, 실제 자동 검사 구현은 Harness 운영 기준에서 다룬다.

| 상태 | 의미 | 완료 판단 |
| --- | --- | --- |
| 통과 | 필수 검증과 필요한 사람 확인을 끝냈고 완료를 막는 위험이 없음 | 완료 가능 |
| 보류 | 검증을 아직 실행하지 않았거나 외부 조건 때문에 완료하지 못함 | 완료 보류 |
| 실패 | 필수 검증이 실패했거나 완료를 막는 위험이 확인됨 | 완료 불가 |
| 허용된 잔여 위험 | 필수 검증은 통과했지만 완료를 막지 않는 일부 위험을 책임자가 승인함 | 승인 근거가 있을 때만 완료 가능 |

필수 검증 실패는 잔여 위험 승인으로 넘기지 않는다. 검증을 실행하지 못한 경우는 먼저 `보류`로 기록한다. 책임자가 후속 조치와 사유를 승인했고 완료를 막지 않는 항목만 `허용된 잔여 위험`으로 바꿀 수 있다.

검증이 실패하거나 완료 근거가 부족하면 다음 순서로 되돌린다.

1. 실패 원인이 코드, 계약, 작업 분해, 검증 절차 중 어디에 있는지 확인한다
2. 원인에 따라 제품 코드, `contracts/`, `tasks.md`, `quickstart.md`를 고친다
3. 기준 commit과 변경 요약을 갱신한다
4. 필요한 검증을 다시 실행한다
5. `verification.md`의 검증 결과와 잔여 위험을 다시 확정한다

## SpecKit 산출물 변경 기준

### 기본 원칙

SpecKit 산출물은 구현 중 발견한 사실에 따라 갱신할 수 있다. 단, `spec.md`, `plan.md`, `contracts/`를 바꾸는 경우에는 변경 내용과 변경 사유를 명확히 남겨야 한다. 이 산출물들은 개발자 개인의 작업 메모가 아니라 협업 기준이므로, 의미 있는 변경은 다른 산출물과 검증 기준에 미치는 영향까지 함께 확인한다.

변경 기록에는 최소한 다음 내용을 남긴다.

- 무엇이 바뀌었는가
- 왜 바뀌었는가
- 어떤 산출물이나 코드 범위에 영향을 주는가
- 어떤 검증 기준을 함께 갱신해야 하는가
- 다른 개발자 또는 다른 Feature에 영향이 있는가

변경 기록 위치는 변경 성격에 따라 정한다.

| 변경 성격 | 기록 위치 |
| --- | --- |
| 요구사항 또는 사용자 흐름 변경 | `spec.md`, PR 본문 |
| 구현 전략 또는 위험 판단 변경 | `plan.md`, PR 본문 |
| 작업 순서나 병렬화 기준 변경 | `tasks.md` |
| 계약 의미 변경 | 변경된 계약 문서, `verification.md`, PR 본문 |
| 검증 절차 변경 | `quickstart.md`, 실행 뒤 `verification.md` |
| 검증 결과 또는 잔여 위험 변경 | `verification.md`, 필요 시 PR 검토 |

### 변경 대상별 처리 기준

이 표는 파일별로 어떤 산출물을 함께 갱신해야 하는지 정한다.

| 변경 대상 | 함께 확인할 위치 |
| --- | --- |
| `spec.md` | 사용자 흐름, 성공 기준, 수용 기준, `plan.md` 영향 |
| `plan.md` | 구현 전략, 기술 선택, 위험 판단, 영향받는 task |
| `tasks.md` | 작업 순서, 병렬화 기준, 완료 상태, Feature 등록부 |
| `quickstart.md` | 예정 검증 절차, 운영자 확인 절차, `verification.md` 기록 방식 |
| `contracts/` | API, 이벤트, 저장 경계, 관측 기준, 예시 데이터 의미, 영향받는 개발자와 사용처 |
| `verification.md` | 실제 검증 결과, 증거 링크, 생략한 검증, 승인된 잔여 위험 |
| `docs/architecture/`, `docs/adr/` | 공유 계약, 보안 경계, 저장 모델, 되돌리기 어려운 결정의 장기 문서 영향 |

### 변경 유형별 처리 기준

| 변경 유형 | 처리 기준 |
| --- | --- |
| 단순 정정 | 오타, 설명 보강, 예시 보완처럼 의미가 바뀌지 않으면 직접 수정한다 |
| 경미한 설계 보정 | 구현 순서, 내부 저장 위치, 검증 방식을 조정하면 `plan.md` 또는 `tasks.md`에 변경 사유를 기록한다 |
| 요구사항 변경 | 사용자 흐름, 성공 기준, 수용 기준이 바뀌면 `spec.md`부터 다시 맞춘다 |
| 구현 전략 변경 | 기술 선택, 작업 순서, 위험 판단이 바뀌면 `plan.md`와 `tasks.md`를 함께 맞춘다 |
| 계약 의미 변경 | 필드명, 필수 여부, 응답 구조, 이벤트 본문, 저장 규약, trace 속성, 예시 데이터 의미가 바뀌면 계약 변경 기준을 적용한다 |
| 검증 결과 변경 | 실행한 검증, 생략한 검증, 운영자 확인 결과가 바뀌면 `verification.md`를 갱신한다 |

### SpecKit 재정리 기준

SpecKit 재정리는 단순 문구 수정이 아니다. 요구사항, 구현 전략, 계약 의미, 검증 절차 중 무엇이 바뀌었는지에 따라 돌아갈 최소 단계를 정한다.

아래 표의 `specify`, `clarify`, `plan`, `tasks`, `analyze`는 SpecKit에서 산출물을 다시 정리할 때 쓰는 단계 이름이다.

| 변경 내용 | 최소 재정리 단계 |
| --- | --- |
| 요구사항, 사용자 흐름, 성공 기준 변경 | `specify` 또는 `clarify`로 `spec.md` 갱신 -> `plan.md` 영향 확인 -> `tasks.md` 갱신 -> `analyze` |
| 구현 전략, 기술 선택, 위험 판단 변경 | `plan.md` 갱신 -> `tasks.md` 갱신 -> 필요 시 `analyze` |
| 작업 순서나 병렬화 기준 변경 | `tasks.md` 갱신 -> Feature 등록부 갱신 |
| 계약 의미 변경 | `contracts/` 갱신 -> 영향받는 `plan.md`, `tasks.md`, `quickstart.md`, `verification.md` 확인 -> 필요 시 `analyze` |
| 검증 절차 변경 | `quickstart.md` 갱신 -> 실행 뒤 `verification.md` 갱신 |
| 단순 문구 정정 | 해당 문서 직접 수정 |

산출물 사이의 불일치가 의심되거나 계약 변경이 다른 개발자, 다른 Agent 작업, 다른 Feature, 공유 경계 기준에 영향을 주면 `analyze` 단계로 교차 점검한다.

### 장기 문서 갱신 기준

`docs/architecture/`와 `docs/adr/`는 모든 Feature에서 수정하지 않는다. 다음처럼 Feature를 넘어 오래 유지될 판단이 생길 때만 갱신한다.

- 여러 Feature가 따를 구조 원칙 변경
- worker, analyzer, API, UI 책임 경계 변경
- 인증 정보, 민감 정보, 외부 입력 같은 보안 경계 변경
- 공유 계약 또는 저장 모델 변경
- 되돌리기 어려운 기술 선택이나 운영 정책 결정

## Harness와 연결

### 역할 경계

Harness와의 연결은 자동 검사 대상으로 넘겨야 하는 산출물을 명확히 하기 위한 것이다.

### 연결 지점

Harness와 연결되는 TCI 산출물은 다음과 같다.

| 산출물 | Harness 연결 방식 |
| --- | --- |
| `specs/<feature-id>/` | Feature 요구, 설계, 작업, 검증 절차 확인 |
| `evidence/<feature-id>/verification.md` | 완료 판단과 잔여 위험 확인 |
| `feature-registry/<feature-id>.yml` | 코드 쓰기 범위, 필수 문서 범위, 공동 수정 영역, 검토와 검사 조건 확인 |
| `boundary-contracts/` | 공유 계약 변경 시 사용처와 승인 범위 확인 |
| `docs/architecture/`, `docs/adr/` | 장기 구조 변경과 되돌리기 어려운 결정의 근거 확인 |

Harness 내부 구조, 필수 자동 검사, PR Gate 실패 처리, Feature 등록부 필드 정의는 Harness 운영 기준에서 다룬다.

검사나 검토에서 산출물 문제가 발견되면 이 문서의 기준에 맞춰 원본 산출물을 먼저 고친다. 예를 들어 완료 근거 누락은 `verification.md`를 보강하고, 계약 변경 누락은 `contracts/`와 영향받는 SpecKit 산출물을 갱신한다.

Feature 등록부의 범위와 실제 변경 범위가 다르면 원인에 따라 처리한다.

- 등록부가 실제 승인 범위를 좁게 적은 경우: `feature-registry/<feature-id>.yml` 갱신
- 코드 변경이 승인 범위를 벗어난 경우: 변경 축소 또는 별도 Feature로 분리
- 여러 Feature가 같은 영역을 건드리는 경우: 공동 수정 영역 승인 기록 추가
- Feature 경계 자체가 잘못 잡힌 경우: `spec.md`, `plan.md`, `tasks.md`를 다시 맞춘 뒤 등록부 갱신
