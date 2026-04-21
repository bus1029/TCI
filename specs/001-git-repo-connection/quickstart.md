# Quickstart: 코드 저장소 연동 설계 검증

## 목적

이 문서는 구현 이후 무엇을 검증해야 설계가 맞게 구현되었는지 빠르게 확인하는 실행 순서를 정의한다. 데모, QA, 작업 분해의 공통 기준으로 사용한다. 검증 기준은 Python 기반 FastAPI API, Celery worker, Jinja2/HTMX 운영 UI 조합을 전제로 한다.

## 사전 조건

1. GitHub Cloud 테스트 저장소 1개 준비
2. 읽기 전용 HTTPS PAT 또는 읽기 전용 SSH 키 준비
3. GitHub webhook 설정 권한과 테스트용 secret 준비
4. FastAPI application, Celery worker, PostgreSQL 16, Redis 7 실행
5. 런타임 디렉터리 `pilot-git-repo-connection/.runtime/git-mirrors`, `pilot-git-repo-connection/.runtime/code-snapshots` 생성
6. 운영자 HTML 화면과 JSON API가 같은 환경 변수 세트를 사용하도록 `pilot-git-repo-connection/src/tci/settings.py` 구성이 끝나 있어야 한다.

## 검증 시나리오

### 1. 저장소 연결 생성 및 검증

1. `POST /api/repository-connections`로 GitHub Cloud 저장소 URL, transport, 기본 ref, credential을 등록한다.
2. 응답이 `pending_verification` 또는 즉시 `active`인지 확인한다.
3. `POST /api/repository-connections/{id}/verify`를 호출해 `git ls-remote` 기반 연결 검증이 수행되는지 확인한다.
4. 잘못된 credential로 같은 요청을 보냈을 때 `reauth_required`와 오류 코드가 반환되는지 확인한다.
5. `GET /api/repository-connections/{id}` 응답에서 `lastSuccessfulSnapshotAt`, `lastFailedSyncAt`, `lastProcessedEvent` 요약 필드가 노출되는지 확인한다.
6. `/connections/{id}` 운영자 화면에서 같은 요약 정보와 traceability 패널이 일관되게 노출되는지 확인한다.

### 2. 범위 규칙 저장 및 경고 확인

1. `POST /api/repository-connections/{id}/scope-rules`에 include/exclude/file type 규칙을 저장한다.
2. 기본 하드 제외 경로와 사용자 규칙이 함께 계산되는지 확인한다.
3. 결과가 0개 파일이 되도록 규칙을 저장했을 때 `empty_result_risk` 경고가 반환되는지 확인한다.
4. `/connections/{id}/scope` 운영자 화면에서 같은 경고 상태와 현재 활성 규칙 버전이 보이는지 확인한다.

### 3. 초기 스냅샷 생성

1. `POST /api/repository-connections/{id}/snapshots`로 수동 초기 수집을 실행한다.
2. `RepositorySyncRun`이 `pending -> running -> succeeded`로 전이되는지 확인한다.
3. 생성된 `CodeSnapshot`에 `resolved_commit_sha`, `scope_rule_version_id`, `file_count`, `archive_path`가 기록되는지 확인한다.
4. `pilot-git-repo-connection/.runtime/code-snapshots/{snapshotId}`에 manifest와 실제 파일이 저장되는지 확인한다.
5. `GET /api/repository-connections/{id}/snapshots/{snapshotId}` 응답에서 `planningInputReference`, `connectionId`, `syncRunId`, `triggerEventId`, `scopeRuleVersionId`를 통해 추적 체인이 보이는지 확인한다.

### 4. Push 이벤트 처리

1. 기본 ref에 새 commit을 push하고 GitHub webhook을 발생시킨다.
2. webhook 엔드포인트가 `202 Accepted`를 즉시 반환하는지 확인한다.
3. 같은 delivery를 재전송했을 때 `duplicate_delivery`로 기록되고 추가 스냅샷이 생성되지 않는지 확인한다.
4. 더 오래된 SHA를 가리키는 이벤트를 재전송했을 때 `stale_head`로 종료되는지 확인한다.
5. Celery task 상태, connection detail의 `lastProcessedEvent`, event timeline 조회 결과가 같은 처리 결론을 보여주는지 확인한다.

### 5. Pull Request 이벤트 처리

1. 기본 ref가 아닌 source branch에서 PR을 생성한다.
2. `opened` 이벤트로 PR source branch 기준 snapshot job이 enqueue되는지 확인한다.
3. source branch에 force push 후 `synchronize` 이벤트를 보냈을 때 최신 `headSha`만 반영되는지 확인한다.
4. `closed` 이벤트는 기록되지만 새 snapshot은 생성되지 않는지 확인한다.
5. `/connections/{id}/events` 운영자 화면에서 PR source branch와 기본 ref 이벤트가 구분되어 보이는지 확인한다.

### 6. webhook 보안 실패

1. 잘못된 secret으로 서명한 요청을 보낸다.
2. `RepositoryEvent.signature_status = secret_mismatch`, `rejection_reason = secret_mismatch`, `processing_status = rejected`가 기록되는지 확인한다.
3. 연결 상세 조회에서 `webhookHealth.status = secret_mismatch_detected`와 마지막 거부 시각이 보이는지 확인한다.
4. payload를 변조해 HMAC이 깨진 요청을 보내고 `signature_status = signature_invalid`, `rejection_reason = signature_invalid`가 기록되는지 확인한다.
5. secret이 없는 연결에 webhook을 보내면 `webhookHealth.status = missing_secret`와 `rejectionReason = secret_missing` 이벤트가 기록되는지 확인한다.

### 7. 운영 상태 전이 회귀

1. 기본 ref를 삭제하거나 이름을 바꾼 뒤 재검증을 실행한다.
2. 연결 상태가 `ref_missing`으로 전환되고 새 ref를 선택하기 전까지 신규 sync run이 차단되는지 확인한다.
3. webhook secret을 회전한 뒤 connection detail에서 `webhookHealth.rotationState`, `webhookHealth.graceUntil`, `webhookHealth.previousSecretDeliveriesDuringGrace`가 보이는지 확인한다.
4. grace window 동안 이전 secret delivery는 허용되고 해당 이벤트에 `verifiedSecretRevisionStatus = previous_grace`가 남는지 확인한다.
5. grace 종료 후에는 같은 이전 secret delivery가 `secret_mismatch`로 거부되는지 확인한다.
6. 이미 정상 처리된 delivery 뒤에 잘못된 replay를 보내도 connection detail의 마지막 정상 이벤트 요약과 webhook health가 오염되지 않는지 확인한다.
7. webhook 미설정 연결의 `/connections/{id}/events` 운영자 화면에서 webhook 상태가 `healthy`가 아니라 `미설정`으로 보이는지 확인한다.
8. event timeline 조회에서 connection detail의 `lastProcessedEvent`와 동일한 마지막 처리 이벤트를 상세 필드로 역추적할 수 있는지 확인한다.

## 필요한 테스트 세트

- Unit
  - scope rule 우선순위 계산
  - 텍스트/바이너리/파일 크기 판정
  - stale SHA 판정
  - webhook 거부 사유 분류(`secret_missing`, `secret_mismatch`, `signature_invalid`)
- Integration
  - 연결 생성/검증 및 상태 전이
  - mirror fetch 후 snapshot archive 생성
  - webhook 서명 검증 및 delivery dedupe
  - ref_missing, secret rotation grace, grace-expiry rejection, bad replay health preservation, webhook health projection
- Contract
  - OpenAPI 요청/응답 스키마 검증
  - GitHub webhook header/body 계약 검증
- End-to-End
  - 연결 생성 -> 규칙 저장 -> 초기 스냅샷 -> Push -> PR synchronize -> secret rotation grace -> traceability 조회 전체 흐름
  - 운영자 HTML 화면에서 connection detail, scope warning, event timeline, snapshot detail이 API 응답과 일치하고 edge-state fallback이 올바른지 확인

## 완료 기준

- 사용자는 10분 이내에 저장소 연결부터 첫 스냅샷 생성 완료까지 확인할 수 있다.
- 유효한 Push/PR 이벤트의 95% 이상이 1분 이내 상태 조회에 반영된다.
- 어떤 snapshot도 연결, ref, 적용 규칙, 트리거 이벤트를 역추적할 수 있다.
- 운영자는 어떤 계획 입력에서 어떤 연결/설정/이벤트/스냅샷이 나왔는지 API 조회만으로 재구성할 수 있다.
- 규칙과 실제 포함 파일 목록의 일치율이 100%다.
