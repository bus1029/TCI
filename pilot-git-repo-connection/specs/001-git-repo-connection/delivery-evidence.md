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

- 상태: 부분 검증 완료
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
  - Unit
    - `tests/unit/repository_connections/test_process_github_event.py::test_evaluate_github_secret_verification_classifies_missing_mismatch_and_invalid`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_accepts_previous_grace_secret_and_marks_revision_status`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_records_ignored_pr_action_without_queueing_sync`
    - `tests/unit/repository_connections/test_process_github_event.py::test_process_github_event_marks_duplicate_delivery_duplicate_head_and_stale_head`
    - `tests/unit/repository_connections/test_webhook_sync_task.py::test_run_webhook_sync_task_marks_event_failed_when_snapshot_build_fails`
  - Integration
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_records_commits_but_queues_single_default_ref_sync`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_webhook_refresh_dedupes_redelivery_without_creating_extra_sync`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_webhook_refresh_skips_stale_head_sha_without_creating_snapshot`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_pull_request_webhook_uses_source_branch_for_allowed_actions_only`
    - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_for_non_default_branch_is_record_only`
  - 실행 결과
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion/test_github_webhook_contract.py','tests/unit/repository_connections/test_process_github_event.py','tests/unit/repository_connections/test_webhook_sync_task.py','tests/integration/repository_connections/test_github_webhook_refresh.py','-q']))"` -> `16 passed`
    - `python -c "import pytest, sys; sys.exit(pytest.main(['tests/contract/repository_ingestion','tests/integration/repository_connections','tests/unit/repository_connections','-q']))"` -> `147 passed, 1 skipped`
  - 아직 남은 검증
    - webhook secret rotation 서비스와 grace continuity 통합 검증
    - 운영 화면 event timeline 검증
    - 상태 반영 지연 `SC-002` 실측

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
  - 현재 측정은 worker/Redis를 생략한 `US1` 기준선 검증이며, full quickstart 회귀는 `T062`에서 다시 확인 예정

### SC-002

- 목표: 유효한 Push/PR 이벤트의 95% 이상이 1분 이내 상태 반영
- 근거:
  - 상태 반영 경로 자체는 `US3` contract/integration 검증으로 확보했다
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py::test_connection_detail_and_event_list_expose_webhook_health_and_last_processed_event`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py::test_push_webhook_records_commits_but_queues_single_default_ref_sync`
  - 실제 지연 시간 측정과 95% 기준 검증은 아직 미실행이며 `T061`에서 별도 확인이 필요하다

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
  - 현재는 판정 로직 단위 검증만 완료된 상태다
  - rotation 서비스와 grace continuity의 통합 검증은 아직 미실행이며 `T052`, `T060`, `T063`과 함께 마무리해야 한다

## 테스트 증거 인덱스

- Unit
  - `tests/unit/repository_connections/test_app.py`
  - `tests/unit/repository_connections/test_scope_filter_engine.py`
  - `tests/unit/repository_connections/test_process_github_event.py`
  - `tests/unit/repository_connections/test_webhook_sync_task.py`
- Integration
  - `tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `tests/integration/repository_connections/test_operator_connection_pages.py`
  - `tests/integration/repository_connections/test_scoped_snapshot.py`
  - `tests/integration/repository_connections/test_operator_scope_pages.py`
  - `tests/integration/repository_connections/test_github_webhook_refresh.py`
- Contract
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
  - `tests/contract/repository_ingestion/test_github_webhook_contract.py`
- End-to-End
  - 아직 미실행 (`US1` 범위는 contract/integration 검증으로 종료)

## 변경 이력

- 2026-04-17: Phase 1 스캐폴드 초안 생성
- 2026-04-20: `US1` 운영 화면 구현 완료, `T029`~`T031` 검증 근거 반영
- 2026-04-20: `US2` 범위 규칙 저장, 필터 엔진, scoped snapshot, 운영 화면, `T032`~`T042` 검증 근거 반영
- 2026-04-20: `US3` webhook intake, event 처리, query API, worker, migration, `T043`~`T044`, `T046`~`T051`, `T053`~`T057` 범위의 부분 검증 근거 반영
