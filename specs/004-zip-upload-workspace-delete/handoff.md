# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

이번 세션은 004 ZIP 업로드/워크스페이스 삭제 기능의 첫 개발 사이클이다. Phase 1 setup과 Phase 2 일부를 TDD로 진행했고, `tasks.md` 기준 T001-T006, T009-T010을 완료했다.

최종 리뷰 루프는 `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer` 모두 추가 수정사항 없음으로 닫혔다. 아직 커밋은 만들지 않았고 작업트리는 dirty 상태다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 완료됨: T001-T006, T009-T010
- 남음: T007, T008, T011-T017과 모든 user story/polish 작업
- 새 증거 문서: `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- 새 migration: `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
- Local Upload API, ZIP extractor, workspace deletion service, operator UI는 아직 구현되지 않았다.

## 이번 세션에서 바뀐 것

- Local Upload와 workspace lifecycle 테스트 패키지 마커를 추가했다.
- ZIP 테스트용 helper와 unsafe archive helper를 추가했다.
- Local Upload ZIP 제한 설정과 기본값을 `Settings`에 추가했다.
- `Workspace`, `LocalUpload`, `WorkspaceDeletionRecord`, source-aware `CodeSnapshot` 모델과 제약을 추가했다.
- Alembic migration으로 workspace, local upload, deletion audit, source-aware snapshot 컬럼을 추가했다.
- 기존 repository-backed snapshot 흐름이 새 `workspace_id`와 `source_kind` 요구사항 아래에서도 깨지지 않도록 repository와 testkit을 보정했다.
- 삭제/삭제중 workspace에서 Git credential binding, ref probe, mirror sync 같은 side effect가 먼저 발생하지 않도록 repository connection 생성과 snapshot build 진입부에 최소 guard를 추가했다.
- `tasks.md`와 `delivery-evidence.md`를 현재 검증 상태로 업데이트했다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py`
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
- `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_models.py`
- `pilot-git-repo-connection/tests/support/local_upload_testkit.py`

## 꼭 유지해야 할 기준

- Local Upload는 GitHub/GitLab `RepositoryConnection` provider로 취급하지 않는다.
- 기존 GitHub/GitLab 응답 필드와 동작은 삭제 workspace guard를 제외하고 유지한다.
- `CodeSnapshot`의 source owner 관계는 DB 제약으로도 막는다.
- Local Upload와 deletion failure message는 bounded/sanitized 형태를 유지한다.
- raw ZIP contents, private file path, credential, token, secret-bearing URL, raw log는 증거 문서나 최종 응답에 기록하지 않는다.
- 실제 operator rehearsal이 필요한 SC 항목은 자동 테스트만으로 완료 처리하지 않는다.
- untracked file 확인에는 `git diff --stat`이 부족하다. 항상 `rtk git status -sb`를 먼저 본다.

## 다시 논의하지 말아야 할 결정

- workspace 삭제는 soft delete다.
- 삭제 시 project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- Local Upload snapshot은 repository connection 없이 독립 source로 저장한다.
- 반복 upload에서는 최신 Local Upload snapshot을 기본값으로 선택한다.
- workspace deletion은 owner/admin 권한과 확인 입력을 요구한다.
- migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.

## 이번 세션에서 얻은 중요한 메모

- PostgreSQL enum 컬럼은 `add_column` 전에 enum type을 명시적으로 생성해야 한다.
- Python 표준 `zipfile`은 encrypted ZIP을 생성하지 못한다. 테스트 helper는 일반 ZIP을 만들고 local/central header의 encrypted bit를 패치한다.
- composite foreign key를 추가하면 SQLAlchemy relationship에 `foreign_keys` 지정이 필요할 수 있다.
- 직접 `Settings(...)` 생성 테스트가 있으므로 새 설정은 dataclass field 기본값을 둬야 한다.
- active workspace guard가 Git side effect 뒤에 있으면 보안 리뷰에서 막힌다. 생성/빌드 진입 초기에 유지해야 한다.
- 광범위 persistence mypy에는 기존 `repository_sync_run_repository.py:287` 타입 이슈가 남아 있었다. 이번 변경 파일에 대한 focused mypy는 clean이다.

## 테스트와 검증 상태

- RED 확인: `rtk proxy pytest -q tests/unit/local_uploads/test_workspace_lifecycle_models.py tests/unit/repository_connections/test_settings.py` 실패. 누락 모델/enum 계약 확인.
- GREEN: `rtk pytest -q tests/unit` 결과 `330 passed`
- GREEN: `rtk pytest -q tests/contract/repository_ingestion` 결과 `152 passed`
- GREEN: focused `rtk mypy ...` 결과 `No issues found`
- GREEN: `rtk black --check src tests alembic/versions/010_local_upload_workspace_delete.py`
- GREEN: `rtk ruff check src tests alembic/versions/010_local_upload_workspace_delete.py`
- GREEN: `rtk git diff --check`
- GREEN: `rtk python -m py_compile alembic/versions/010_local_upload_workspace_delete.py`
- GREEN: `rtk alembic heads` 결과 `010_local_upload_workspace_del (head)`
- 리뷰: `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer` 최종 no findings

아직 실제 PostgreSQL DB에 migration upgrade/downgrade를 적용하지 않았다. 현재 확인은 migration syntax, Alembic head, 모델/테스트 기반 검증이다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 파일부터 확인한다.
2. 이 파일, `tasks.md`, `delivery-evidence.md`를 읽고 완료 범위를 맞춘다.
3. T007 repository tests와 T008 workspace guard tests를 먼저 RED로 추가한다.
4. T011 workspace repository, T012 local upload repository, T013 source-aware snapshot persistence, T014 shared workspace lifecycle guard를 구현한다.
5. T015 app dependency wiring과 T016 testkit fake 보정을 진행한다.
6. T017의 foundational checks를 실행한다.
7. reviewer loop를 다시 돌리고 수정사항이 없어질 때까지 반복한다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 첫 개발 사이클의 리뷰 수정사항 반영과 evidence 업데이트였다.

바로 다음 액션은 T007/T008 실패 테스트를 작성해 다음 foundational TDD 사이클을 시작하는 것이다.

## 병렬 작업과 소유권

이번 세션의 reviewer agents는 read-only 리뷰만 수행했고 파일을 직접 수정하지 않았다. 다음 세션에서 병렬 agent를 쓴다면 write ownership은 겹치지 않게 나누는 편이 안전하다.

- T007 담당: `tests/unit/local_uploads/test_source_aware_snapshot_repository.py`
- T008 담당: `tests/unit/local_uploads/test_workspace_lifecycle_guard.py`
- 메인 담당: repository/service 구현과 최종 통합
