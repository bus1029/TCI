# 짧은 요약

- 이번 세션은 `$tdd`로 `US3` credential boundary 일부를 진행했다.
- 완료 처리된 항목은 `T050`, `T051`, `T061`이다.
- `T052`, `T062`, `T063`은 event/status 경로 커버가 아직 없어 다시 미완료로 유지했다.
- `candidateId`가 있으면 configured candidate source를 실제 조회하고, source 없음/identity mismatch는 create 전에 거부한다.
- 개인 provider candidate grant는 operation credential로 저장하지 않는다. 테스트에서 저장된 credential을 복호화해 workspace credential인지 확인한다.
- verify, snapshot collect, scope preview, default-ref reverify는 active + read-only validated workspace operation credential만 사용한다.
- reviewer loop를 돌렸고 최종 general/security/Python re-review는 no findings였다.
- 커밋은 아직 하지 않았다.

# 현재 상태

- 브랜치: `003-repository-first-connections`
- 현재 `git status -sb` 기준:
  - `003-repository-first-connections...origin/003-repository-first-connections`
  - staged 변경 없음
  - 작업트리 변경 있음
- 변경 파일:
  - `pilot-git-repo-connection/src/tci/domain/services/build_code_snapshot.py`
  - `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - `pilot-git-repo-connection/src/tci/domain/services/evaluate_scope_rule_warning.py`
  - `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `pilot-git-repo-connection/src/tci/domain/services/update_default_ref.py`
  - `pilot-git-repo-connection/src/tci/domain/services/verify_repository_connection.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_connection_and_initial_snapshot.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
  - `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - `pilot-git-repo-connection/tests/unit/repository_connections/test_repository_connection_credentials.py`
  - `specs/003-repository-first-connections/delivery-evidence.md`
  - `specs/003-repository-first-connections/tasks.md`
  - `specs/003-repository-first-connections/handoff.md`
- `tasks.md` 현재 기준:
  - 완료: `T017-T029`, `T031-T047`, `T049-T051`, `T055-T061`
  - 미완료: `T030`, `T048`, `T052-T054`, `T062-T067`, Final phase `T068-T073`
- `SC-001`과 `SC-004`는 실제 운영자 리허설이 없어 미완료다.

# 이번 세션에서 바뀐 것

- `repository_connection_support.py`
  - `OperationCredential`, `OperationCredentialRevision` protocol, `require_active_operation_credential()`를 추가했다.
  - operation credential은 `CredentialRevisionStatus.ACTIVE`이고 `read_only_validated=True`일 때만 허용한다.
  - inactive, revoked, previous_grace, unvalidated, missing credential은 `CONNECTION_AUTH_FAILED`로 거부한다.
- `verify_repository_connection.py`
  - 검증 경로가 active workspace read-only operation credential만 사용한다.
  - 부적격 credential이면 git resolve/probe 없이 `REAUTH_REQUIRED`로 전환한다.
- `build_code_snapshot.py`
  - snapshot collect 경로가 active workspace read-only operation credential만 사용한다.
  - 부적격 credential이면 sync run을 auth failure로 실패시키고 connection을 `REAUTH_REQUIRED`로 전환한다.
- `evaluate_scope_rule_warning.py`
  - scope preview도 operation credential helper를 사용한다.
  - revoked/unvalidated credential이면 git 호출 없이 `PREVIEW_FAILED`를 반환한다.
- `update_default_ref.py`
  - default-ref update/reverify 경로가 operation credential helper를 사용한다.
  - 부적격 credential이면 `REAUTH_REQUIRED`로 전환하고 기존 ref를 보존한다.
- `create_repository_connection.py`
  - `candidateId`가 있으면 `repository_candidate_source`를 조회한다.
  - candidate source가 없으면 `INVALID_INPUT`으로 거부한다.
  - candidate가 없거나 workspace가 다르거나 canonical repository identity가 submitted remote와 다르면 create 전에 거부한다.
  - candidate personal grant는 operation credential로 저장하지 않고 submitted workspace credential만 검증/저장한다.
- `test_repository_connection_credentials.py`
  - operation credential helper의 active/read-only/missing/revoked/unvalidated 단위 테스트를 추가했다.
- `test_repository_first_permission_failures.py`
  - candidate personal grant가 저장 credential이 아님을 복호화 검증으로 확인한다.
  - invalid shared read-only credential, candidate identity mismatch, candidate source missing이 side effect 없이 거부되는지 검증한다.
- `test_repository_operation_credential_boundary.py`
  - verify, snapshot collect, scope preview, default-ref reverify가 revoked credential로 git 호출하지 않는지 검증한다.
- `test_connection_and_initial_snapshot.py`
  - candidate/manual duplicate regression이 실제 candidate source를 주입하도록 조정했다.
- `tasks.md`
  - `T050`, `T051`, `T061` 완료.
  - `T052`, `T062`, `T063`은 event/status 커버가 남아 있어 미완료 유지.
- `delivery-evidence.md`
  - credential boundary RED/GREEN, reviewer remediation, 최종 re-review 결과를 기록했다.
  - `FR-003b`, `FR-012`, `FR-012b`, `SC-007`은 여전히 partial로 유지했다.

# 다음 에이전트가 먼저 봐야 할 파일

- `specs/003-repository-first-connections/tasks.md`
  - 현재 완료/미완료 task 기준선. 특히 `T052`, `T062`, `T063`이 open인 이유 확인.
- `specs/003-repository-first-connections/delivery-evidence.md`
  - 이번 credential boundary RED/GREEN, reviewer loop, 남은 evidence gap.
- `pilot-git-repo-connection/src/tci/domain/services/repository_connection_support.py`
  - `require_active_operation_credential()` 계약.
- `pilot-git-repo-connection/src/tci/domain/services/create_repository_connection.py`
  - candidate source validation과 submitted workspace credential 저장 경계.
- `pilot-git-repo-connection/src/tci/domain/services/evaluate_scope_rule_warning.py`
  - scope preview credential boundary 적용 지점.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_first_permission_failures.py`
  - candidate grant와 create failure side-effect regression.
- `pilot-git-repo-connection/tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - verify/collect/scope-preview/reverify boundary regression.

# 꼭 유지해야 할 기준

- 새 repository connection create는 `planningInputReferenceId` 또는 planning/spec/plan 출처 필드를 받지 않아야 한다.
- obsolete planning/spec/plan field는 compatibility로 수용하지 말고 `400 INVALID_INPUT`으로 거부해야 한다.
- `candidateId`만으로 active connection을 만들면 안 된다.
- `candidateId`가 있으면 configured candidate source로 후보를 확인해야 한다. source가 없으면 manual create처럼 처리하지 말고 거부해야 한다.
- candidate source 결과와 submitted remote의 canonical repository identity가 다르면 create 전에 거부해야 한다.
- candidate source가 반환한 항목은 requested `workspace_id`와 일치해야 한다.
- candidate `remoteUrl`은 credential, token, query, fragment, unsafe scheme, malformed host/port/path를 echo하지 않아야 한다.
- candidate discovery 개인 grant는 operation credential로 저장하거나 승격하지 않아야 한다.
- operation credential은 active + read-only validated workspace credential이어야 한다.
- rejected create는 connection/credential/event/sync side effect를 만들지 않아야 한다.
- API validation error와 web form error는 credential secret을 echo하지 않아야 한다.
- duplicate precheck는 git ref resolve, credential probe, mirror sync 전에 실패해야 한다.
- GitLab SSH remote의 명시적 포트는 allowlist에서 포트까지 요구해야 한다. `:443`도 SSH에서는 default HTTPS port로 취급하지 않는다.
- 새 workspace 기반 connection은 `planning_input_reference_id=None`이어야 한다.
- legacy planning trace는 같은 workspace에 속할 때만 보존/노출해야 한다.
- cross-workspace planning reference의 `sourceReference`, `approvedSpecPath`, `approvedPlanPath`는 connection detail과 snapshot detail에서 노출하지 않아야 한다.
- `connections/index.html`이 create/list 통합 템플릿이다. nonexistent `connections/create.html`, `connections/list.html` 경로를 다시 쓰지 말아야 한다.
- `SC-001`, `SC-004`는 실제 운영자 리허설 없이 완료 처리하지 말아야 한다.

# 다시 논의하지 말아야 할 결정

- repository-first create에서 planning/spec/plan reference를 요구하지 않는다.
- obsolete planning/spec/plan create field는 호환 수용하지 않고 명시적으로 거부한다.
- `origin`은 detail-only가 아니라 create/list/detail response와 operator UI 이해 모델에 필요하다.
- `origin` 계산 ownership은 domain helper와 detail/list service projection으로 둔다. serializer는 fallback만 제공한다.
- GitHub/GitLab provider semantics, webhook 의미, snapshot trigger rule은 이번 범위에서 재설계하지 않는다.
- 후보 목록 기반 판단 지원은 `US3` 범위다. `US1` MVP는 수동 URL 입력으로 독립 검증한다.
- persisted legacy row의 workspace scope는 기존 `workspace_id`를 canonical로 사용한다.
- cross-workspace planning reference는 legacy trace 보존 대상이 아니다. compatibility 상태로 보여주고 trace 내용은 숨긴다.
- canonical identity helper는 candidate list와 create duplicate precheck의 shared source로 유지한다.

# 이번 세션에서 얻은 중요한 메모

- `T052`, `T062`, `T063`은 일부 구현/테스트가 생겼지만 완료가 아니다.
  - 현재 커버된 경로: create, verify, snapshot collect, scope preview, default-ref reverify.
  - 아직 남은 경로: event/status operation credential boundary와 operation-appropriate remediation.
- reviewer loop 중 주요 지적과 조치:
  - scope preview가 credential helper를 우회했다 → 수정 및 regression 추가.
  - `candidateId` test가 source 호출을 증명하지 못했다 → source call count와 mismatch/source-missing regression 추가.
  - encrypted secret 문자열에 plaintext가 없는지 보는 테스트는 무의미했다 → 복호화 후 workspace credential인지 검증.
  - helper 인자가 duck typing이었다 → `Protocol`과 enum 직접 비교로 고정.
  - event/status까지 완료했다고 과대 표시했다 → `T052/T062/T063`을 open으로 되돌리고 evidence를 partial로 낮춤.
- `cmux`는 사용 가능하다. 현재 workspace는 `workspace:1`, 기존 focused pane은 `pane:1`이었다.

# 테스트와 검증 상태

- RED:
  - `rtk proxy pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: `require_active_operation_credential` 미구현 import failure.
- GREEN:
  - `rtk pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: `10 passed`, 이후 reviewer remediation 후 `12 passed`.
- Reviewer remediation RED:
  - `rtk proxy pytest tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: candidate source 미호출, candidate identity mismatch create 허용, scope preview revoked credential 사용으로 `3 failed`.
- Reviewer remediation GREEN:
  - `rtk pytest tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py -q`
  - 결과: `7 passed`.
  - `rtk pytest tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py tests/integration/repository_connections/test_connection_and_initial_snapshot.py::test_candidate_selected_connection_reuses_manual_duplicate_precheck -q`
  - 결과: `14 passed`.
- 최종 broad regression:
  - `rtk pytest tests/unit/repository_connections tests/integration/repository_connections tests/contract/repository_ingestion -q`
  - 결과: `592 passed`.
- 최종 static checks:
  - `rtk black --check .`
  - 결과: `162 files would be left unchanged`.
  - `rtk ruff check .`
  - 결과: no issues found.
  - focused `rtk mypy src/tci/domain/services/repository_connection_support.py src/tci/domain/services/create_repository_connection.py src/tci/domain/services/evaluate_scope_rule_warning.py src/tci/domain/services/verify_repository_connection.py src/tci/domain/services/build_code_snapshot.py src/tci/domain/services/update_default_ref.py tests/unit/repository_connections/test_repository_connection_credentials.py tests/integration/repository_connections/test_repository_first_permission_failures.py tests/integration/repository_connections/test_repository_operation_credential_boundary.py`
  - 결과: no issues found.
  - `rtk alembic heads`
  - 결과: `009_repository_first_connections (head)`.
  - `rtk proxy git diff --check`
  - 결과: 통과.
- 최종 reviewer loop:
  - General reviewer: final no findings.
  - Security reviewer: final no remaining security/credential findings.
  - Python reviewer: final no findings. Broad `mypy .`는 기존 baseline typing issue가 있어 touched-scope mypy를 사용했다.
- dependency/lockfile 변경은 없다. dependency audit는 실행하지 않았다.

# 다음 세션의 시작 순서

1. `git status -sb`로 staged/unstaged 상태를 확인한다.
2. 현재 변경을 커밋할지 결정한다.
   - 이번 세션에서 `$git-commit pilot-git-repo-connection` scoped commit message를 생성했다.
   - docs 변경(`tasks.md`, `delivery-evidence.md`, `handoff.md`)은 `pilot-git-repo-connection` scoped commit message에는 포함하지 않았다.
3. 계속 개발하면 `T052/T062/T063`의 남은 event/status operation credential boundary부터 시작한다.
4. 그 다음 `T048/T064-T066` operator candidate UI로 넘어간다.
5. 이후 `T053/T054` mixed-provider separation/identification evidence를 진행한다.
6. 새 작업도 RED/GREEN과 reviewer loop 결과를 `delivery-evidence.md`에 이어서 기록한다.

# 마지막 액션과 바로 다음 액션

- 마지막 액션:
  - `handoff.md`를 현재 세션 기준으로 갱신했다.
  - 직전 최종 검증은 모두 통과했다.
  - Cmux 새 pane에서 동일 세션 resume과 `$git-commit pilot-git-repo-connection` 요청을 실행하려고 준비했다.
- 바로 다음 액션:
  - 커밋 여부를 결정한다.
  - 커밋하지 않고 계속 개발하면 `T052/T062/T063` event/status credential boundary를 TDD로 이어간다.

# 병렬 작업과 소유권

- 이번 세션에서 reviewer subagent를 사용했다. 모두 read-only였고 파일 수정은 메인 세션에서만 수행했다.
- 사용한 reviewer:
  - General reviewer: scope preview bypass, candidate source 미검증, task/evidence overclaim을 지적했다. remediation 후 final no findings.
  - Security reviewer: scope preview bypass, evidence overclaim, encrypted secret test gap을 지적했다. remediation 후 final no remaining security/credential findings.
  - Python reviewer: helper typing/duck typing과 test 검증 약점을 지적했다. remediation 후 final no findings.
- Cmux:
  - `cmux` CLI 사용 가능.
  - 현재 workspace는 `workspace:1`.
