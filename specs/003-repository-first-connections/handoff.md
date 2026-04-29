# 짧은 요약

- `003-repository-first-connections` Foundation 범위 `T001-T016` 구현 완료.
- 리뷰어 루프 반복 완료. 최종 일반/Python/DB/Security 리뷰 모두 `no findings` 또는 `approve`.
- 다음 세션은 커밋 전 diff 검토 후 `tasks.md`의 다음 미완료 작업부터 시작하면 된다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 작업 범위: `specs/003-repository-first-connections/tasks.md`의 Foundation `T001-T016`.
- `tasks.md`에서 `T001-T016`은 `[x]`로 체크되어 있다.
- 핵심 구현은 `pilot-git-repo-connection` 하위 Python/FastAPI/SQLAlchemy/Alembic 코드다.
- `rtk black .`를 repo-wide로 실행해 기존 미포맷 Python 파일 35개도 포맷됐다.
- 현재 worktree는 많은 수정 파일과 신규 파일을 포함한다. 정상 상태다. 아직 커밋 전이다.

# 이번 세션에서 바뀐 것

- `specs/003-repository-first-connections/delivery-evidence.md` 신규 작성.
  - FR/SC 커버리지 맵과 검증 명령 기록.
- `specs/003-repository-first-connections/tasks.md` 수정.
  - `T001-T016` 완료 표시.
- `pilot-git-repo-connection/alembic/versions/009_repository_first_connections.py` 신규 작성.
  - `repository_connections.planning_input_reference_id` nullable.
  - `collection_scope_rule_versions.planning_input_reference_id` nullable.
  - GitHub/GitLab provider별 unique index 추가.
  - `CREATE UNIQUE INDEX CONCURRENTLY` 사용.
  - GitHub canonical `provider_project_path` check를 `NOT VALID` 후 `VALIDATE CONSTRAINT`로 추가.
  - downgrade 전 repository-first nullable row 존재 시 중단.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/models.py` 수정.
  - planning reference nullable typing 반영.
  - GitHub canonical path DB check 반영.
  - provider별 repository identity unique index 반영.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py` 수정.
  - 새 연결은 `planning_input_reference_id=None`.
  - obsolete planning trace 없이 create.
  - duplicate preflight를 credential encryption/git access 전 실행.
  - concurrent duplicate race 방지를 위해 repository identity creation lock 구간 안에서 duplicate check, secret encryption, git probe, mirror sync, final insert 수행.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py` 수정.
  - `ensure_repository_identity_available(...)` 추가.
  - PostgreSQL에서는 `pg_advisory_xact_lock` 기반 `repository_identity_creation_lock(...)` 추가.
  - non-PostgreSQL 테스트 환경에서는 no-op lock.
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py` 수정.
  - `CreateRepositoryConnectionRequest`에서 `planningInputReferenceId` 제거.
  - `extra="forbid"`로 obsolete planning 필드 차단.
  - base response에 `origin` 추가.
  - nullable `planningInputReference` 직렬화 추가.
- `pilot-git-repo-connection/src/tci/app.py` 수정.
  - validation error에서 `input`, `ctx`, `url` 제거.
  - `/api/repository-connections` obsolete planning 필드는 `400 INVALID_INPUT` 반환.
  - secret-bearing validation echo 방지.
- `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py` 및 `src/tci/web/templates/connections/index.html` 수정.
  - operator form에서 `planningInputReferenceId` 제거.
  - web POST에서 obsolete planning/spec/plan field 차단.
  - error rerender 시 `credentialSecret` 제거.
- snapshot/detail/traceability 관련 서비스와 manifest writer 수정.
  - planning reference가 `None`이어도 snapshot/detail/manifest 직렬화 가능.
  - manifest에서 null planning reference는 JSON `null`, 문자열 `"None"` 아님.
- 테스트 신규 추가.
  - `tests/integration/repository_connections/test_repository_first_migration.py`
  - `tests/support/repository_first_connection_testkit.py`
  - `tests/unit/repository_connections/test_repository_connection_origin.py`
  - `tests/unit/repository_connections/test_repository_connection_serialization.py`
  - `tests/unit/repository_connections/test_repository_operation_credentials.py`
  - `tests/unit/repository_connections/test_snapshot_traceability.py`
- 기존 repository ingestion 테스트 다수 수정.
  - planning reference가 create payload 필수가 아니게 된 점 반영.
  - `ruff F841` unused planning locals 제거.
  - `black .`로 프로젝트 전체 formatting 정리.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md` - 완료된 `T001-T016`과 다음 미완료 task 확인.
- `specs/003-repository-first-connections/delivery-evidence.md` - 이번 세션 검증 기록과 커버리지 근거.
- `pilot-git-repo-connection/alembic/versions/009_repository_first_connections.py` - migration 핵심.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py` - repository-first create 흐름과 identity lock.
- `pilot-git-repo-connection/src/tci/infrastructure/persistence/repository_connection_repository.py` - duplicate preflight와 advisory lock.
- `pilot-git-repo-connection/src/tci/api/schemas/repository_connection.py` - request/response shape 변화.
- `pilot-git-repo-connection/src/tci/app.py` - validation error redaction과 obsolete field rejection.
- `pilot-git-repo-connection/src/tci/web/routes/repository_connections.py` - web form obsolete field 처리.
- `pilot-git-repo-connection/tests/contract/repository_ingestion/test_repository_connection_contract.py` - create contract, duplicate, lock 관련 검증.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId`를 받지 않아야 한다.
- 새 connection은 `planning_input_reference_id=None`이어야 한다.
- legacy planning trace는 삭제하거나 덮어쓰지 말아야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- GitHub `provider_project_path`는 DB에서 `repository_owner || '/' || repository_name`와 일치해야 하고 `NULL`을 허용하면 안 된다.
- GitLab identity unique key는 `workspace_id`, `provider`, `provider_instance_url`, `provider_project_path` 기준을 유지해야 한다.
- duplicate create는 credential encryption/git access 전에 차단되어야 한다.
- PostgreSQL 환경에서는 repository identity lock이 `pg_advisory_xact_lock`으로 동작해야 한다.
- migration index는 concurrent로 생성해야 한다.
- check constraint는 `NOT VALID` 후 `VALIDATE CONSTRAINT` 흐름을 유지해야 한다.
- downgrade는 repository-first nullable row가 있으면 중단해야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 명시적으로 거부한다.
- `origin`은 detail-only가 아니라 base create/list response에도 포함한다.
- GitHub repository identity는 `provider_project_path`를 canonical owner/name으로 DB에서 강제한다.
- duplicate create race는 final unique index만으로 충분하지 않다. credential/git access 전 identity lock이 필요하다.
- repo-wide `black .` 적용은 완료했다. formatter 변경을 임의로 되돌리지 말아야 한다.

# 이번 세션에서 얻은 중요한 메모

- PostgreSQL `CHECK`는 `UNKNOWN`을 통과시킨다. `provider_project_path = ...`만 쓰면 `NULL`이 빠져나간다.
  - 현재 조건은 `provider_project_path IS NOT NULL AND provider_project_path = ...` 형태다.
- SQLAlchemy naming convention 때문에 raw check constraint name은 drift를 만들 수 있다.
  - migration은 `conv(...)`와 PostgreSQL preparer로 convention-compatible 이름을 렌더링한다.
- duplicate preflight만으로는 concurrent create race를 막지 못한다.
  - 현재 create flow는 identity lock 안에서 duplicate check, encryption, git access, insert를 수행한다.
- `rtk black .`가 변경 파일 외 기존 미포맷 파일 35개도 정리했다.
  - diff가 넓어진 이유다.
- `pip-audit`, `safety`는 로컬에서 unavailable로 리뷰어가 보고했다.
  - 이번 세션은 dependency/lockfile 변경 없음.
- full `mypy .`는 기존 광범위 typing noise가 있다고 리뷰어가 언급했다.
  - 이번 변경 경로와 새 테스트에 대한 focused mypy는 통과했다.

# 테스트와 검증 상태

- 최종 검증 통과.
- 실행한 주요 명령:
  - `rtk black --check .`
    - 결과: `152 files would be left unchanged`.
  - `rtk ruff check .`
    - 결과: no issues found.
  - `rtk mypy src/tci/app.py src/tci/api/schemas/repository_connection.py src/tci/domain/services/create_repository_connection.py src/tci/infrastructure/persistence/repository_connection_repository.py src/tci/infrastructure/persistence/models.py src/tci/infrastructure/snapshots/snapshot_manifest_writer.py tests/unit/repository_connections/test_repository_connection_serialization.py tests/unit/repository_connections/test_snapshot_traceability.py tests/support/repository_connection_testkit.py`
    - 결과: no issues found.
  - `rtk alembic heads`
    - 결과: `009_repository_first_connections (head)`.
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
    - 결과: `550 passed`.
- 리뷰어 최종 상태:
  - DB reviewer: no blocking findings.
  - Security reviewer: no blocking findings.
  - Python reviewer: approve.
  - General reviewer: approve.
- 미검증 또는 잔여 리스크:
  - full `mypy .`는 이번 세션 최종으로 돌리지 않았다. 기존 project-wide typing noise가 있다고 리뷰어가 언급했다.
  - dependency audit는 도구 부재로 실행하지 못했다. dependency 변경 없음.

# 다음 세션의 시작 순서

1. `rtk git status --short`로 현재 변경 목록 확인.
2. `rtk git diff --stat`와 핵심 파일 diff를 검토.
3. `specs/003-repository-first-connections/tasks.md`에서 `T017` 이후 다음 미완료 작업 확인.
4. 커밋이 필요하면 이번 Foundation 변경을 하나의 커밋으로 묶을지, formatting 변경을 분리할지 결정.
5. 다음 user story 작업 전 `delivery-evidence.md`에 새 검증 항목을 이어서 기록.

# 마지막 액션과 바로 다음 액션

- 마지막 액션: reviewer 경고를 모두 닫고 `black --check .`, `ruff`, focused `mypy`, Alembic head, repository ingestion pytest `550 passed` 확인.
- 바로 다음 액션: 커밋 전 diff review. 특히 repo-wide `black .`로 넓어진 formatting-only 변경과 기능 변경을 구분해서 확인.

# 병렬 작업과 소유권

- 이번 세션에서 reviewer subagent를 반복 사용했다.
- 최종 승인:
  - General reviewer `019dd844-7321-7e53-a825-901a5e55792e`: approve.
  - Python reviewer `019dd844-720e-72d3-9307-f2ccb8b8f994`: approve.
  - DB reviewer `019dd839-99b0-7ca2-87c9-4815ed13d762`: no blocking findings.
  - Security reviewer `019dd839-9800-74f3-b1de-f2da7c094f8d`: no blocking findings.
- 모든 subagent는 close 완료.
