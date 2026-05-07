# Handoff: ZIP 업로드 스냅샷과 워크스페이스 삭제

## 짧은 요약

004 ZIP 업로드/워크스페이스 삭제 기능의 Phase 2 foundation 개발 사이클을 완료했다. `tasks.md` 기준 T001-T017이 완료됐고, Local Upload와 workspace lifecycle의 모델, migration, repository, source-aware snapshot persistence, app dependency wiring, testkit fake가 구현됐다.

리뷰 루프에서 repository connection 생성, default-ref update, webhook secret rotation, GitHub/GitLab webhook 처리의 deleting/deleted workspace race를 같이 닫았다. `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer` follow-up까지 no findings로 종료했다.

## 현재 상태

- 현재 브랜치: `004-zip-upload-workspace-delete`
- 완료됨: T001-T017
- 다음 작업: T018부터 User Story 1 ZIP validation test-first 개발
- 작업트리는 dirty 상태이며 커밋은 만들지 않았다.
- `rtk git status -sb` 기준 브랜치는 `origin/004-zip-upload-workspace-delete`보다 `ahead 1`이다.
- 관련 없는 untracked path `mvp1-features/...`가 있다. 이번 feature scope가 아니므로 건드리지 말아야 한다.
- 아직 미구현: Local Upload API, ZIP extractor, Local Upload snapshot creation service, workspace deletion service, archive purge, operator UI

## 이번 세션에서 바뀐 것

- `Workspace`, `LocalUpload`, `WorkspaceDeletionRecord`, source-aware `CodeSnapshot` 모델과 DB 제약을 추가했다.
- Alembic 010 migration `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`를 추가했다.
- `workspace_repository.py`, `local_upload_repository.py`, `workspace_lifecycle.py`, `failure_messages.py`를 새로 추가했다.
- `CodeSnapshotRepository`에 Local Upload draft creation, source owner validation, workspace/source scoped lookup, latest Local Upload snapshot lookup을 추가했다.
- `app.py` dependencies와 `repository_connection_testkit.py` fake repositories를 Phase 2 infrastructure에 맞춰 확장했다.
- Existing GitHub/GitLab flow가 새 workspace/source 제약 아래에서도 동작하도록 repository snapshot, sync run, webhook, default-ref update 경로를 보정했다.
- Repository connection 생성은 same-identity external Git side effect를 session advisory lock으로 serialize하되, nested advisory self-deadlock과 idle transaction을 피하도록 조정했다.
- Webhook secret plaintext는 connection/workspace validation 이후 service 내부에서 생성하도록 순서를 바꿨다.
- GitHub/GitLab webhook은 deleting/deleted workspace에서 event, cursor, sync run, health mutation 없이 `WORKSPACE_NOT_ACTIVE`로 중단한다.
- `specs/004-zip-upload-workspace-delete/tasks.md`와 `delivery-evidence.md`를 현재 검증 상태로 갱신했다.

## 다음 에이전트가 먼저 봐야 할 파일

- `specs/004-zip-upload-workspace-delete/tasks.md`
- `specs/004-zip-upload-workspace-delete/delivery-evidence.md`
- `pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/workspace_repository.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/local_upload_repository.py`
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/code_snapshot_repository.py`
- `pilot-git-repo-connection/src/tci/domain/services/workspace_lifecycle.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_source_aware_snapshot_repository.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_lifecycle_guard.py`
- `pilot-git-repo-connection/tests/unit/local_uploads/test_workspace_local_upload_repositories.py`
- `pilot-git-repo-connection/tests/support/repository_connection_testkit.py`

## 꼭 유지해야 할 기준

- Local Upload는 GitHub/GitLab `RepositoryConnection` provider가 아니다.
- Source owner 관계는 `source_kind`와 owner FK/check로 강제한다.
- 기존 GitHub/GitLab 응답 필드와 provider semantics는 삭제 workspace guard를 제외하고 유지한다.
- Deleting/deleted workspace에서는 새 external Git side effect, secret write, event/cursor/sync/health mutation을 시작하지 않는다.
- Raw ZIP contents, private file path, credential, token, secret-bearing URL, raw log는 docs/evidence/final response에 기록하지 않는다.
- 실제 operator rehearsal이 필요한 SC 항목은 자동 테스트만으로 완료 처리하지 않는다.
- untracked 파일 확인에는 `git diff --stat`이 부족하다. 항상 `rtk git status -sb`를 먼저 본다.

## 다시 논의하지 말아야 할 결정

- workspace 삭제는 soft delete다.
- 삭제 시 project contents와 snapshot archive 파일은 purge하고, 최소 audit metadata만 남긴다.
- Local Upload snapshot은 repository connection 없이 독립 source로 저장한다.
- 반복 upload에서는 최신 Local Upload snapshot을 기본값으로 선택한다.
- workspace deletion은 owner/admin 권한과 확인 입력을 요구한다.
- migration revision id는 Alembic 길이 제약 때문에 `010_local_upload_workspace_del`로 둔다.
- Phase 2에서 강화한 existing GitHub/GitLab deleting-workspace guard는 full US2 deletion flow를 대체하지 않는다.

## 이번 세션에서 얻은 중요한 메모

- PostgreSQL enum 컬럼은 dependent column 추가 전에 enum type을 명시적으로 생성해야 한다.
- Composite FK를 추가하면 SQLAlchemy relationship에 `foreign_keys` 지정이 필요할 수 있다.
- Direct `Settings(...)` 생성 테스트가 있으므로 새 settings field에는 dataclass 기본값이 필요하다.
- Advisory lock으로 external Git side effect를 serialize할 때 inner transaction advisory lock을 다시 잡으면 self-deadlock이 날 수 있다.
- `Session(expire_on_commit=False)` 상태에서는 external Git 이후 같은 session 재조회가 identity-map stale read가 될 수 있다. `expire_all()` 또는 fresh read가 필요하다.
- Webhook secret plaintext는 missing connection/workspace validation 뒤에 생성해야 한다.

## 테스트와 검증 상태

- GREEN: focused Phase 2/regression pytest `222 passed`
- GREEN: focused mypy `No issues found`
- GREEN: `rtk black --check pilot-git-repo-connection/src/tci pilot-git-repo-connection/tests`
- GREEN: `rtk ruff check pilot-git-repo-connection/src/tci pilot-git-repo-connection/tests`
- GREEN: `rtk git diff --check`
- GREEN: `rtk python -m py_compile pilot-git-repo-connection/alembic/versions/010_local_upload_workspace_delete.py`
- GREEN: `rtk alembic heads` result `010_local_upload_workspace_del (head)`
- 리뷰: `reviewer`, `python-reviewer`, `database-reviewer`, `security-reviewer` follow-up까지 no findings
- 미검증: 실제 PostgreSQL DB에 migration upgrade/downgrade 적용은 아직 하지 않았다.

## 다음 세션의 시작 순서

1. `rtk git status -sb`로 dirty/untracked 파일을 확인한다.
2. `specs/004-zip-upload-workspace-delete/tasks.md`와 `delivery-evidence.md`로 T001-T017 완료 상태를 확인한다.
3. T018 ZIP validation tests를 먼저 RED로 작성한다.
4. T019 Local Upload snapshot service tests를 RED로 추가한다.
5. T023 safe ZIP central-directory validation과 entry normalization을 최소 구현한다.
6. T024-T026 storage/manifest/service를 이어서 GREEN으로 만든다.
7. User Story 1 scope가 커지면 reviewer loop를 다시 돌린다.

## 마지막 액션과 바로 다음 액션

마지막 액션은 Phase 2 foundation 구현, reviewer/security no-findings closure, `tasks.md`/`delivery-evidence.md`/`handoff.md` 갱신이었다.

바로 다음 액션은 T018의 실패 테스트를 `pilot-git-repo-connection/tests/unit/local_uploads/test_local_zip_extractor.py`에 작성하고 RED를 확인하는 것이다.

## 병렬 작업과 소유권

다음 세션에서 병렬 agent를 쓴다면 write ownership은 겹치지 않게 나누는 편이 안전하다.

- T018 담당: `tests/unit/local_uploads/test_local_zip_extractor.py`
- T019 담당: `tests/unit/local_uploads/test_create_local_upload_snapshot.py`
- 메인 담당: `local_zip_extractor.py`, snapshot archive/manifest/service 구현과 통합
