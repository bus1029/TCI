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

- 상태: 미검증
- 범위
  - GitHub webhook 수신
  - Push/PR 최신화
  - dedupe와 stale head 처리
  - secret rotation grace
  - event timeline 조회
- 근거
  - TODO

## FR-014 추적성 근거

- 계획 입력 -> 연결 설정
  - `test_connection_detail_exposes_traceability_and_placeholder_summaries`
  - `test_connection_detail_page_renders_summary_guidance_and_traceability`
- 연결 설정 -> scope rule version
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_save_scope_rule_returns_warning_and_latest_scope_projection`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`
- trigger event -> sync run
  - `US1` 범위에서는 수동 초기 수집만 다루므로 `triggerEventId = null`이 계약대로 유지된다.
- sync run -> code snapshot
  - `test_connection_detail_reflects_latest_snapshot_after_manual_initial_snapshot`
  - `test_scoped_snapshot_stores_filtered_files_and_scope_version`
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
- 근거: TODO

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
- 근거: TODO

## 테스트 증거 인덱스

- Unit
  - `tests/unit/repository_connections/test_app.py`
  - `tests/unit/repository_connections/test_scope_filter_engine.py`
- Integration
  - `tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `tests/integration/repository_connections/test_operator_connection_pages.py`
  - `tests/integration/repository_connections/test_scoped_snapshot.py`
  - `tests/integration/repository_connections/test_operator_scope_pages.py`
- Contract
  - `tests/contract/repository_ingestion/test_repository_connection_contract.py`
  - `tests/contract/repository_ingestion/test_repository_scope_contract.py`
- End-to-End
  - 아직 미실행 (`US1` 범위는 contract/integration 검증으로 종료)

## 변경 이력

- 2026-04-17: Phase 1 스캐폴드 초안 생성
- 2026-04-20: `US1` 운영 화면 구현 완료, `T029`~`T031` 검증 근거 반영
- 2026-04-20: `US2` 범위 규칙 저장, 필터 엔진, scoped snapshot, 운영 화면, `T032`~`T042` 검증 근거 반영
