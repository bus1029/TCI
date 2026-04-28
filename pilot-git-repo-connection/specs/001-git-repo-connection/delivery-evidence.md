# Delivery Evidence

## 목적

이 문서는 `001-git-repo-connection` 구현이 어떤 검증 근거로 완료되었는지 기록한다. 각 사용자 스토리의 검증 결과와 `FR-014`, `SC-001`부터 `SC-005`까지의 근거를 한곳에서 추적할 수 있어야 한다.

## 문서 사용 규칙

- 구현 중간에는 섹션과 기대 근거만 먼저 준비
- 실제 검증이 끝난 뒤 실행 로그, 테스트 결과, 수동 검증 링크를 채움
- 스토리별 완료 판단과 전체 릴리스 판단을 분리해서 기록

## 사용자 스토리 검증

### User Story 1

- 상태: 검증 완료
- 범위
  - 저장소 연결 생성
  - 기본 ref 검증
  - 초기 스냅샷 생성
  - traceability 기본 조회
- 근거
  - Contract
    - `tests/contract/repository_ingestion/test_repository_connection_contract.py::test_create_connection_rejects_unsupported_provider`
    - `tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_connection_detail_returns_null_last_processed_event_and_traceability`
  - Integration
    - `tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
    - `tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_default_ref_change_updates_future_target_without_erasing_existing_state`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_renders_empty_state_and_create_form`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_page_renders_existing_connection_summary`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_redirects_to_detail_page`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connection_detail_page_renders_summary_guidance_and_traceability`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_does_not_echo_secret_after_validation_error`
    - `tests/integration/repository_connections/test_operator_connection_pages.py::test_connections_create_route_rejects_cross_origin_submission`
  - 실행 결과
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/integration/repository_connections/test_operator_connection_pages.py','tests/integration/repository_connections/test_connection_and_initial_snapshot.py','tests/unit/repository_connections/test_app.py','tests/contract/repository_ingestion/test_repository_connection_contract.py','-q']))"` -> `34 passed`

### User Story 2

- 상태: 검증 완료
- 범위
  - 범위 규칙 저장
  - `empty_result_risk` 경고
  - `NO_INCLUDED_FILES` 실패 처리
  - scope rule version 추적
- 근거
  - Contract
    - `tests/contract/repository_ingestion/test_repository_scope_contract.py::test_scope_rule_routes_require_workspace_header`
    - `tests/contract/repository_ingestion/test_repository_scope_contract.py::test_save_scope_rule_returns_warning_and_latest_scope_projection`
    - `tests/contract/repository_ingestion/test_repository_scope_contract.py::test_save_scope_rule_rejects_non_positive_max_file_size`
    - `tests/contract/repository_ingestion/test_repository_scope_contract.py::test_save_scope_rule_tolerates_preview_failure_and_still_saves_rule`
  - Unit
    - `tests/unit/repository_connections/test_scope_filter_engine.py::test_scope_filter_engine_applies_include_exclude_and_file_type_in_defined_order`
    - `tests/unit/repository_connections/test_scope_filter_engine.py::test_scope_filter_engine_keeps_v1_hard_excluded_files_out_even_when_included`
  - Integration
    - `tests/integration/repository_connections/test_scoped_snapshot.py::test_scoped_snapshot_stores_filtered_files_and_scope_version`
    - `tests/integration/repository_connections/test_scoped_snapshot.py::test_scoped_snapshot_fails_when_scope_rule_excludes_everything`
    - `tests/integration/repository_connections/test_operator_scope_pages.py::test_scope_page_renders_current_warning_state`
    - `tests/integration/repository_connections/test_operator_scope_pages.py::test_scope_page_save_redirects_back_to_scope_view`
    - `tests/integration/repository_connections/test_operator_scope_pages.py::test_scope_page_rejects_non_positive_max_file_size`
  - 실행 결과
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion/test_repository_connection_contract.py','tests/contract/repository_ingestion/test_repository_scope_contract.py','tests/integration/repository_connections/test_connection_and_initial_snapshot.py','tests/integration/repository_connections/test_scoped_snapshot.py','tests/integration/repository_connections/test_operator_connection_pages.py','tests/integration/repository_connections/test_operator_scope_pages.py','tests/unit/repository_connections/test_scope_filter_engine.py','tests/unit/repository_connections/test_app.py','-q']))"` -> `45 passed`

### User Story 3

- 상태: 검증 완료
- 범위
  - GitHub webhook 수신
  - Push/PR 최신화
  - dedupe와 stale head 처리
  - secret rotation grace
  - event timeline 조회
- 근거
  - Contract
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_receive_github_webhook_accepts_verified_push_and_returns_accepted_payload`
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_receive_github_webhook_rejects_when_secret_is_missing`
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_receive_github_webhook_distinguishes_secret_mismatch_from_signature_invalid`
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_receive_github_webhook_rejects_repository_mismatch`
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_receive_github_webhook_handles_rejected_redelivery_idempotently`
    - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_connection_detail_and_event_list_expose_webhook_health_and_last_processed_event`
    - `tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_connection_detail_exposes_webhook_rotation_projection`
  - Unit
    - `tests/unit/repository_connections/test_process_github_event.py::test_evaluate_github_secret_verification_classifies_missing_mismatch_and_invalid`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_accepts_previous_grace_secret_and_marks_revision_status`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_records_ignored_pr_action_without_queueing_sync`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_marks_duplicate_delivery_duplicate_head_and_stale_head`
    - `tests/unit/repository_connections/test_webhook_sync_task.py::test_run_webhook_sync_task_marks_event_failed_when_snapshot_build_fails`
    - `tests/unit/repository_connections/test_rotate_webhook_secret.py::test_rotate_webhook_secret_replaces_active_secret_and_starts_grace_window`
  - Integration
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_records_commits_but_queues_single_default_ref_sync`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_webhook_refresh_dedupes_redelivery_without_creating_extra_sync`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_webhook_refresh_skips_stale_head_sha_without_creating_snapshot`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_pull_request_webhook_uses_source_branch_for_allowed_actions_only`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_for_non_default_branch_is_record_only`
    - `tests/integration/repository_connections/test_operator_event_pages.py::test_connection_detail_page_renders_webhook_health_and_event_timeline_link`
    - `tests/integration/repository_connections/test_operator_event_pages.py::test_repository_events_page_renders_event_timeline_items`
  - 실행 결과
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion/test_github_webhook_contract.py','tests/unit/repository_connections/test_process_github_event.py','tests/unit/repository_connections/test_webhook_sync_task.py','tests/integration/repository_connections/test_github_webhook_refresh.py','-q']))"` -> `16 passed`
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion','tests/integration/repository_connections','tests/unit/repository_connections','-q']))"` -> `147 passed, 1 skipped`
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion/test_repository_connection_contract.py','tests/contract/repository_ingestion/test_github_webhook_contract.py','tests/integration/repository_connections/test_operator_connection_pages.py','tests/integration/repository_connections/test_operator_event_pages.py','tests/unit/repository_connections/test_rotate_webhook_secret.py','-q']))"` -> `32 passed`

### Polish & Cross-Cutting

- 상태: 검증 완료
- 범위
  - `reauth_required` / `ref_missing` / 추가 ref 안내 회귀
  - grace 만료 후 이전 secret 거부
  - bad replay 이후 operator 상태 보존
  - webhook 상태 반영 지연 실측
  - quickstart API/queue 통합 플로우 재검증
- 근거
  - Integration
    - `tests/integration/repository_connections/test_edge_state_regression.py::test_reauth_required_connection_preserves_operator_guidance`
    - `tests/integration/repository_connections/test_edge_state_regression.py::test_ref_missing_connection_preserves_operator_guidance`
    - `tests/integration/repository_connections/test_edge_state_regression.py::test_previous_secret_delivery_is_rejected_after_grace_expiry`
    - `tests/integration/repository_connections/test_edge_state_regression.py::test_bad_replay_does_not_overwrite_last_processed_event_or_health`
    - `tests/integration/repository_connections/test_webhook_status_latency.py::test_webhook_status_projection_latency_stays_within_sla`
    - `tests/integration/repository_connections/test_quickstart_validation.py::test_quickstart_validation_covers_release_scope_flow`
  - 실행 결과
    - `python -m pytest pilot-git-repo-connection/tests/integration/repository_connections/test_edge_state_regression.py pilot-git-repo-connection/tests/integration/repository_connections/test_webhook_status_latency.py pilot-git-repo-connection/tests/integration/repository_connections/test_quickstart_validation.py -q` -> `6 passed`
    - `python tests/support/measure_webhook_status_latency.py` -> `SC002_SAMPLE_COUNT=5`, `SC002_COMPLETED_SAMPLE_COUNT=5`, `SC002_MAX_SECONDS=0.007271`, `SC002_P95_SECONDS=0.007271`
    - `python tests/support/run_quickstart_validation.py` -> `SC001_FIRST_SNAPSHOT_SECONDS=0.015385`, `MANUAL_SNAPSHOT_ID=...`, `WEBHOOK_SNAPSHOT_ID=...`, `PUSH_EVENT_PROCESSING_STATUS=completed`, `PR_EVENT_PROCESSING_STATUS=completed`, `GRACE_ACCEPTED=True`, `EXPIRED_REJECTION_CODE=WEBHOOK_SECRET_MISMATCH`
  - 범위 주의
    - quickstart harness는 public API route와 queue task 경로를 검증한다.
    - 운영자 HTML surface parity는 기존 `test_operator_connection_pages.py`, `test_operator_event_pages.py`, `test_operator_scope_pages.py`가 별도로 담당한다.
  - 환경 차단
    - 실제 PostgreSQL destructive migration smoke는 `TCI_TEST_DATABASE_URL`, `TCI_ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1` 미설정으로 아직 미실행

## FR-014 추적성 근거

- 계획 입력 -> 연결 설정
  - `test_connection_detail_exposes_traceability_and_placeholder_summaries`
  - `test_connection_detail_page_renders_summary_guidance_and_traceability`
- 연결 설정 -> scope rule version
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_save_scope_rule_returns_warning_and_latest_scope_projection`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`
- trigger event -> sync run
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_connection_detail_and_event_list_expose_webhook_health_and_last_processed_event`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_records_commits_but_queues_single_default_ref_sync`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_webhook_refresh_dedupes_redelivery_without_creating_extra_sync`
- sync run -> code snapshot
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`
  - webhook-triggered snapshot detail의 `triggerEventId` 반영은 구현됐지만 별도 검증은 아직 추가하지 못했다
- code snapshot -> snapshot manifest
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`

## 성공 기준 검증

### SC-001

- 목표: 저장소 연결부터 첫 스냅샷 완료 확인까지 10분 이내
- 근거:
  - 재현 스크립트: `python tests/support/measure_us1_first_snapshot.py`
  - 로컬 인메모리 검증에서 연결 생성 -> 초기 스냅샷 생성 -> 스냅샷 상세 조회까지 `0.0111초`
  - quickstart 통합 helper(`python tests/support/run_quickstart_validation.py`) 기준 연결 생성 -> scope 저장 -> API-triggered manual snapshot -> snapshot 상세 조회까지 `0.015385초`
  - 현재 측정은 로컬 통합 하네스 기준선이며, 둘 다 `SC-001`의 10분 한계를 충분히 하회한다

### SC-002

- 목표: 유효한 Push/PR 이벤트의 95% 이상이 1분 이내 상태 반영
- 근거:
  - 상태 반영 경로 자체는 `US3` contract/integration 검증으로 확보했다
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_connection_detail_and_event_list_expose_webhook_health_and_last_processed_event`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_records_commits_but_queues_single_default_ref_sync`
  - `tests/integration/repository_connections/test_webhook_status_latency.py::test_webhook_status_projection_latency_stays_within_sla`
  - 재현 스크립트: `python tests/support/measure_webhook_status_latency.py`
  - helper 실측 결과: `5` samples, `completed=5`, `p95=0.007271초`, `max=0.007271초`
  - 현재 수치는 public webhook route -> queue task -> completed projection까지 포함한 로컬 통합 하네스 기준이며 `SC-002`의 1분 SLA 한계를 충분히 하회한다

### SC-003

- 목표: 모든 스냅샷의 저장소, ref, 규칙, 수집 시점 추적 가능
- 근거:
  - `test_get_connection_detail_returns_null_last_processed_event_and_traceability`
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_connection_detail_page_renders_summary_guidance_and_traceability`

### SC-004

- 목표: 규칙과 실제 스냅샷 결과의 일치율 100%
- 근거:
  - `test_scope_filter_engine_applies_include_exclude_and_file_type_in_defined_order`
  - `test_scope_filter_engine_keeps_v1_hard_excluded_files_out_even_when_included`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`
  - `test_scoped_snapshot_fails_when_scope_rule_excludes_everything`

### SC-005

- 목표: webhook secret 회전 grace 기간 동안 유효 이벤트 중단 없이 처리
- 근거:
  - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_accepts_previous_grace_secret_and_marks_revision_status`
  - `tests/unit/repository_connections/test_rotate_webhook_secret.py::test_rotate_webhook_secret_replaces_active_secret_and_starts_grace_window`
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py::test_get_connection_detail_exposes_webhook_rotation_projection`
  - `tests/integration/repository_connections/test_operator_event_pages.py::test_connection_detail_page_renders_webhook_health_and_event_timeline_link`
  - `tests/integration/repository_connections/test_edge_state_regression.py::test_previous_secret_delivery_is_rejected_after_grace_expiry`
  - `tests/integration/repository_connections/test_quickstart_validation.py::test_quickstart_validation_covers_release_scope_flow`
  - quickstart helper 실측 결과(`python tests/support/run_quickstart_validation.py`): grace 기간의 이전 secret delivery는 수용되고, grace 만료 후 동일 secret은 `WEBHOOK_SECRET_MISMATCH`로 거부된다

## 테스트 증거 인덱스

- Unit
  - `tests/unit/repository_connections/test_app.py`
  - `tests/unit/repository_connections/test_scope_filter_engine.py`
  - `tests/unit/repository_connections/test_process_github_event.py`
  - `tests/unit/repository_connections/test_webhook_sync_task.py`
- Integration
  - `tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `tests/integration/repository_connections/test_operator_connection_pages.py`
  - `tests/integration/repository_connections/test_operator_event_pages.py`
  - `tests/integration/repository_connections/test_scoped_snapshot.py`
  - `tests/integration/repository_connections/test_operator_scope_pages.py`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py`
  - `tests/integration/repository_connections/test_edge_state_regression.py`
  - `tests/integration/repository_connections/test_webhook_status_latency.py`
  - `tests/integration/repository_connections/test_quickstart_validation.py`
- Contract
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py`
- End-to-End
  - 별도 browser E2E는 아직 미실행
  - quickstart release-flow는 `tests/integration/repository_connections/test_quickstart_validation.py`의 API/queue integration harness로 검증

## 변경 이력

- 2026-04-17: Phase 1 스캐폴드 초안 생성
- 2026-04-20: `US1` 운영 화면 구현 완료, `T029`~`T031` 검증 근거 반영
- 2026-04-20: `US2` 범위 규칙 저장, 필터 엔진, scoped snapshot, 운영 화면, `T032`~`T042` 검증 근거 반영
- 2026-04-20: `US3` webhook intake, event 처리, query API, worker, migration, `T043`~`T044`, `T046`~`T051`, `T053`~`T057` 범위의 부분 검증 근거 반영
- 2026-04-20: `US3` webhook secret rotation service, connection detail rotation projection, 운영 event timeline 화면, `T045`, `T052`, `T055`, `T058`, `T059` 근거 반영
