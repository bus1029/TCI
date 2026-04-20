from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import shutil
import uuid

from tci.api.problem_details import ProblemCode
from tci.domain.services.repository_connection_support import (
    RepositoryConnectionProblem,
    bind_git_credential,
    decrypt_secret_from_storage,
)
from tci.domain.services.scope_filter_engine import (
    filter_snapshot_entries,
    rule_set_from_scope_rule,
)
from tci.infrastructure.git.git_mirror_manager import GitMirrorSyncError
from tci.infrastructure.persistence.code_snapshot_repository import (
    CodeSnapshotDraft,
    CodeSnapshotFileDraft,
)
from tci.infrastructure.persistence.models import (
    DefaultRefType,
    RefType,
    RepositoryConnectionStatus,
    SyncFailureCode,
    SyncRunStatus,
)


@dataclass(frozen=True, slots=True)
class BuildCodeSnapshotCommand:
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    sync_run_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SnapshotBuildContext:
    connection_id: uuid.UUID
    planning_input_reference_id: uuid.UUID
    remote_url: str
    transport: object
    requested_ref_type: object
    requested_ref_name: str
    sync_run_status: SyncRunStatus
    credential_type: object | None
    encrypted_secret: str | None


def build_code_snapshot(command, *, dependencies):
    if dependencies.session_factory is None:
        raise RuntimeError("코드 스냅샷을 생성하려면 데이터베이스 세션이 필요합니다.")

    context = _load_snapshot_context(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        sync_run_id=command.sync_run_id,
        dependencies=dependencies,
    )
    if context.sync_run_status is SyncRunStatus.SUCCEEDED:
        snapshot = _load_existing_snapshot(
            sync_run_id=command.sync_run_id,
            dependencies=dependencies,
        )
        if snapshot is None:
            raise LookupError("완료된 스냅샷 실행의 결과를 찾을 수 없습니다.")
        return snapshot
    if context.sync_run_status is not SyncRunStatus.PENDING:
        raise RepositoryConnectionProblem(
            ProblemCode.INVALID_INPUT,
            "대기 중인 스냅샷 실행만 처리할 수 있습니다.",
        )

    _mark_sync_run_running(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        sync_run_id=command.sync_run_id,
        dependencies=dependencies,
    )

    if context.credential_type is None or context.encrypted_secret is None:
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=SyncFailureCode.AUTH_FAILED,
            failure_message="활성 자격 증명을 찾을 수 없습니다.",
            connection_status=RepositoryConnectionStatus.REAUTH_REQUIRED,
            dependencies=dependencies,
        )

    try:
        credential_secret = decrypt_secret_from_storage(
            context.encrypted_secret,
            settings=dependencies.settings,
        )
        with bind_git_credential(
            remote_url=context.remote_url,
            transport=context.transport,
            credential_type=context.credential_type,
            credential_secret=credential_secret,
        ) as credential_bound_remote_url:
            resolved_ref = dependencies.git_ref_resolver.resolve(
                remote_url=credential_bound_remote_url,
                ref_type=_resolver_ref_type(context.requested_ref_type),
                ref_name=context.requested_ref_name,
            )
            mirror = dependencies.git_mirror_manager.ensure_synced_mirror(
                connection_id=context.connection_id,
                remote_url=credential_bound_remote_url,
                restore_remote_url=(
                    None
                    if credential_bound_remote_url == context.remote_url
                    else context.remote_url
                ),
            )
            materialized_snapshot = dependencies.git_mirror_manager.read_snapshot_entries(
                mirror=mirror,
                commit_sha=resolved_ref.commit_sha,
            )
    except Exception as error:
        failure_code, connection_status, failure_message = _classify_snapshot_failure(error)
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=failure_code,
            failure_message=failure_message,
            connection_status=connection_status,
            dependencies=dependencies,
        )

    if not materialized_snapshot.entries:
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=SyncFailureCode.NO_INCLUDED_FILES,
            failure_message="기본 수집 정책을 적용한 결과 스냅샷에 포함할 파일이 없습니다.",
            connection_status=None,
            dependencies=dependencies,
        )

    scope_rule_version = _ensure_active_scope_rule_version(
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        dependencies=dependencies,
    )
    filtered_entries = filter_snapshot_entries(
        entries=materialized_snapshot.entries,
        rule_set=rule_set_from_scope_rule(scope_rule_version),
    )
    if not filtered_entries:
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=SyncFailureCode.NO_INCLUDED_FILES,
            failure_message="범위 규칙을 적용한 결과 스냅샷에 포함할 파일이 없습니다.",
            connection_status=None,
            dependencies=dependencies,
        )

    try:
        snapshot_id = uuid.uuid4()
        archive = dependencies.snapshot_archive_store.store(
            snapshot_id=snapshot_id,
            entries=filtered_entries,
        )
        traceability = dependencies.snapshot_traceability_builder(
            planning_input_reference_id=context.planning_input_reference_id,
            connection_id=context.connection_id,
            scope_rule_version_id=scope_rule_version.id,
            sync_run_id=command.sync_run_id,
            snapshot_id=snapshot_id,
        )
        dependencies.snapshot_manifest_writer.write(
            archive=archive,
            traceability=traceability,
        )
    except Exception as error:
        if "archive" in locals():
            shutil.rmtree(archive.absolute_path, ignore_errors=True)
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
            failure_message=str(error) or "스냅샷 저장에 실패했습니다.",
            connection_status=None,
            dependencies=dependencies,
        )

    now = datetime.now(tz=UTC)
    try:
        with dependencies.session_factory() as session:
            snapshot_repository = dependencies.code_snapshot_repository_factory(session)
            sync_run_repository = dependencies.repository_sync_run_repository_factory(
                session
            )
            connection_repository = dependencies.repository_connection_repository_factory(
                session
            )
            snapshot = snapshot_repository.create(
                draft=CodeSnapshotDraft(
                    id=snapshot_id,
                    connection_id=context.connection_id,
                    sync_run_id=command.sync_run_id,
                    scope_rule_version_id=scope_rule_version.id,
                    requested_ref_type=context.requested_ref_type,
                    requested_ref_name=context.requested_ref_name,
                    resolved_commit_sha=resolved_ref.commit_sha,
                    tree_sha=materialized_snapshot.tree_sha,
                    archive_path=archive.archive_path,
                    file_count=len(archive.files),
                    total_bytes=sum(file.size_bytes for file in archive.files),
                ),
                files=tuple(
                    CodeSnapshotFileDraft(
                        path=file.path,
                        extension=file.extension,
                        language_hint=file.language_hint,
                        size_bytes=file.size_bytes,
                        content_sha256=file.content_sha256,
                        archive_blob_path=file.archive_blob_path,
                        included_by=file.included_by,
                    )
                    for file in archive.files
                ),
            )
            sync_run_repository.mark_succeeded(
                connection_id=context.connection_id,
                sync_run_id=command.sync_run_id,
                resolved_commit_sha=resolved_ref.commit_sha,
                completed_at=now,
            )
            connection_repository.record_snapshot_success(
                workspace_id=command.workspace_id,
                connection_id=context.connection_id,
                succeeded_at=now,
            )
            return snapshot
    except Exception as error:
        shutil.rmtree(archive.absolute_path, ignore_errors=True)
        return _fail_snapshot_build(
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
            sync_run_id=command.sync_run_id,
            failure_code=SyncFailureCode.SNAPSHOT_WRITE_FAILED,
            failure_message=str(error) or "스냅샷 메타데이터 저장에 실패했습니다.",
            connection_status=None,
            dependencies=dependencies,
        )


def _load_snapshot_context(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, sync_run_id: uuid.UUID, dependencies
):
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        credential_repository = dependencies.credential_revision_repository_factory(session)
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        connection = connection_repository.get(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if connection is None:
            raise LookupError("저장소 연결을 찾을 수 없습니다.")
        sync_run = sync_run_repository.get(
            connection_id=connection.id,
            sync_run_id=sync_run_id,
        )
        if sync_run is None:
            raise LookupError("스냅샷 실행 이력을 찾을 수 없습니다.")
        credential_revision = credential_repository.get_active_for_connection(
            connection_id=connection.id
        )
        return SnapshotBuildContext(
            connection_id=connection.id,
            planning_input_reference_id=connection.planning_input_reference_id,
            remote_url=connection.remote_url,
            transport=connection.transport,
            requested_ref_type=sync_run.requested_ref_type,
            requested_ref_name=sync_run.requested_ref_name,
            sync_run_status=sync_run.status,
            credential_type=(
                None if credential_revision is None else credential_revision.credential_type
            ),
            encrypted_secret=(
                None
                if credential_revision is None
                else credential_revision.encrypted_secret
            ),
        )


def _mark_sync_run_running(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, sync_run_id: uuid.UUID, dependencies
) -> None:
    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        sync_run_repository.mark_running(
            connection_id=connection_id,
            sync_run_id=sync_run_id,
            started_at=datetime.now(tz=UTC),
        )


def _load_existing_snapshot(*, sync_run_id: uuid.UUID, dependencies):
    with dependencies.session_factory() as session:
        snapshot_repository = dependencies.code_snapshot_repository_factory(session)
        return snapshot_repository.get_by_sync_run_id(sync_run_id=sync_run_id)


def _ensure_default_scope_rule_version(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    with dependencies.session_factory() as session:
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        return connection_repository.ensure_default_scope_rule_version(
            workspace_id=workspace_id,
            connection_id=connection_id,
            created_by=workspace_id,
        )


def _ensure_active_scope_rule_version(
    *, workspace_id: uuid.UUID, connection_id: uuid.UUID, dependencies
):
    with dependencies.session_factory() as session:
        scope_rule_repository = dependencies.scope_rule_repository_factory(session)
        scope_rule = scope_rule_repository.get_active_for_connection(
            workspace_id=workspace_id,
            connection_id=connection_id,
        )
        if scope_rule is not None:
            return scope_rule
    return _ensure_default_scope_rule_version(
        workspace_id=workspace_id,
        connection_id=connection_id,
        dependencies=dependencies,
    )


def _classify_snapshot_failure(
    error: Exception,
) -> tuple[SyncFailureCode, RepositoryConnectionStatus | None, str]:
    problem_code = getattr(error, "problem_code", None)
    if problem_code == ProblemCode.CONNECTION_AUTH_FAILED:
        return (
            SyncFailureCode.AUTH_FAILED,
            RepositoryConnectionStatus.REAUTH_REQUIRED,
            str(error) or "저장소 자격 증명 검증에 실패했습니다.",
        )
    if problem_code == ProblemCode.DEFAULT_REF_NOT_FOUND:
        return (
            SyncFailureCode.REF_NOT_FOUND,
            RepositoryConnectionStatus.REF_MISSING,
            str(error) or "기본 분석 대상 ref를 찾을 수 없습니다.",
        )
    if isinstance(error, RepositoryConnectionProblem):
        return (
            SyncFailureCode.AUTH_FAILED,
            RepositoryConnectionStatus.REAUTH_REQUIRED,
            error.detail or "저장소 자격 증명 검증에 실패했습니다.",
        )
    if isinstance(error, GitMirrorSyncError):
        return (
            SyncFailureCode.MIRROR_SYNC_FAILED,
            None,
            str(error) or "Git mirror 동기화에 실패했습니다.",
        )
    return (
        SyncFailureCode.MIRROR_SYNC_FAILED,
        None,
        str(error) or "Git mirror 동기화에 실패했습니다.",
    )


def _fail_snapshot_build(
    *,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    failure_code: SyncFailureCode,
    failure_message: str,
    connection_status: RepositoryConnectionStatus | None,
    dependencies,
):
    problem = RepositoryConnectionProblem(
        ProblemCode.CONNECTION_AUTH_FAILED
        if failure_code is SyncFailureCode.AUTH_FAILED
        else ProblemCode.DEFAULT_REF_NOT_FOUND
        if failure_code is SyncFailureCode.REF_NOT_FOUND
        else ProblemCode.NO_INCLUDED_FILES
        if failure_code is SyncFailureCode.NO_INCLUDED_FILES
        else ProblemCode.INVALID_INPUT,
        failure_message,
    )
    now = datetime.now(tz=UTC)
    with dependencies.session_factory() as session:
        sync_run_repository = dependencies.repository_sync_run_repository_factory(session)
        connection_repository = dependencies.repository_connection_repository_factory(
            session
        )
        sync_run_repository.mark_failed(
            connection_id=connection_id,
            sync_run_id=sync_run_id,
            failure_code=failure_code,
            failure_message=failure_message,
            completed_at=now,
        )
        connection_repository.record_sync_failure(
            workspace_id=workspace_id,
            connection_id=connection_id,
            failed_at=now,
            status=connection_status,
        )
    raise problem


def _resolver_ref_type(requested_ref_type):
    if requested_ref_type is RefType.PULL_REQUEST_BRANCH:
        return DefaultRefType.BRANCH
    return requested_ref_type
