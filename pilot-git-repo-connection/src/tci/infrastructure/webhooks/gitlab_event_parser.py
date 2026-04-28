from __future__ import annotations

from datetime import UTC, datetime

from tci.infrastructure.persistence.models import (
    DomainEventType,
    EventTargetKind,
    ProviderEventType,
    RefType,
    SyncTriggerType,
)
from tci.infrastructure.webhooks.provider_event_types import ParsedProviderEvent


MAX_GITLAB_REF_NAME_CHARS = 255


def parse_gitlab_event_payload(
    *,
    event_name: str,
    payload: dict[str, object],
    received_at: datetime | None = None,
) -> ParsedProviderEvent:
    occurred_at = received_at or datetime.now(tz=UTC)
    repository_full_name = _repository_full_name(payload)
    object_kind = _read_nullable_string(payload.get("object_kind"))
    _validate_event_kind(event_name=event_name, object_kind=object_kind)
    if event_name == "Push Hook" or object_kind == "push":
        ref_name = _read_gitlab_ref(payload.get("ref"), prefix="refs/heads/")
        return ParsedProviderEvent(
            provider_event_type=ProviderEventType.PUSH,
            provider_action=None,
            domain_event_type=DomainEventType.PUSH_RECEIVED,
            target_kind=EventTargetKind.DEFAULT_REF,
            repository_full_name=repository_full_name,
            target_key="default_ref",
            target_ref_name=ref_name,
            target_head_sha=_read_git_head_sha(
                payload.get("checkout_sha") or payload.get("after")
            ),
            requested_ref_type=RefType.BRANCH,
            requested_ref_name=ref_name,
            trigger_type=SyncTriggerType.WEBHOOK_PUSH,
            occurred_at=occurred_at,
            commit_shas=_commit_shas_from_push(payload),
        )
    if event_name == "Tag Push Hook" or object_kind == "tag_push":
        tag_name = _read_gitlab_ref(payload.get("ref"), prefix="refs/tags/")
        return ParsedProviderEvent(
            provider_event_type=ProviderEventType.PUSH,
            provider_action=None,
            domain_event_type=DomainEventType.PUSH_RECEIVED,
            target_kind=EventTargetKind.DEFAULT_REF,
            repository_full_name=repository_full_name,
            target_key="default_ref",
            target_ref_name=tag_name,
            target_head_sha=_read_git_head_sha(
                payload.get("checkout_sha") or payload.get("after")
            ),
            requested_ref_type=RefType.TAG,
            requested_ref_name=tag_name,
            trigger_type=SyncTriggerType.WEBHOOK_PUSH,
            occurred_at=occurred_at,
            commit_shas=_commit_shas_from_push(payload),
        )
    if event_name == "Merge Request Hook" or object_kind == "merge_request":
        attributes = payload.get("object_attributes") or {}
        if not isinstance(attributes, dict):
            attributes = {}
        action = _read_nullable_string(attributes.get("action"))
        iid = attributes.get("iid")
        last_commit = attributes.get("last_commit") or {}
        if not isinstance(last_commit, dict):
            last_commit = {}
        source_branch = _read_ref_name(attributes.get("source_branch"))
        oldrev = _read_nullable_string(attributes.get("oldrev"))
        is_code_moving = action in {"open", "opened", "reopen", "reopened"} or (
            action in {"update", "updated"} and oldrev is not None
        )
        return ParsedProviderEvent(
            provider_event_type=ProviderEventType.MERGE_REQUEST,
            provider_action=action,
            domain_event_type=DomainEventType.MR_RECEIVED,
            target_kind=EventTargetKind.MERGE_REQUEST_SOURCE,
            repository_full_name=repository_full_name,
            target_key=f"mr:{iid}",
            target_ref_name=source_branch,
            target_head_sha=_read_git_head_sha(last_commit.get("id")),
            requested_ref_type=RefType.BRANCH,
            requested_ref_name=source_branch,
            trigger_type=SyncTriggerType.WEBHOOK_MERGE_REQUEST,
            occurred_at=occurred_at,
            is_code_moving=is_code_moving,
            source_project_path=_source_project_path(payload),
            commit_shas=_commit_shas_from_merge_request(last_commit),
        )
    return ParsedProviderEvent(
        provider_event_type=ProviderEventType.UNKNOWN,
        provider_action=None,
        domain_event_type=DomainEventType.SIGNATURE_REJECTED,
        target_kind=EventTargetKind.NONE,
        repository_full_name=repository_full_name,
        target_key="none",
        target_ref_name=None,
        target_head_sha=None,
        requested_ref_type=None,
        requested_ref_name=None,
        trigger_type=None,
        occurred_at=occurred_at,
        is_code_moving=False,
    )


def _repository_full_name(payload: dict[str, object]) -> str | None:
    project = payload.get("project") or payload.get("repository") or {}
    if not isinstance(project, dict):
        return None
    return _read_nullable_string(
        project.get("path_with_namespace") or project.get("full_path")
    )


def _source_project_path(payload: dict[str, object]) -> str | None:
    project = payload.get("source_project") or {}
    if not isinstance(project, dict):
        return None
    return _read_nullable_string(
        project.get("path_with_namespace") or project.get("full_path")
    )


def _read_nullable_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _read_ref_name(value: object) -> str | None:
    ref_name = _read_nullable_string(value)
    if ref_name is not None and len(ref_name) > MAX_GITLAB_REF_NAME_CHARS:
        raise ValueError("GitLab webhook ref 이름이 너무 깁니다.")
    return ref_name


def _read_gitlab_ref(value: object, *, prefix: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError("GitLab webhook ref 형식이 올바르지 않습니다.")
    ref_name = _read_ref_name(value.removeprefix(prefix))
    if not ref_name:
        raise ValueError("GitLab webhook ref 형식이 올바르지 않습니다.")
    return ref_name


def _validate_event_kind(*, event_name: str, object_kind: str | None) -> None:
    expected_kind_by_event = {
        "Push Hook": "push",
        "Tag Push Hook": "tag_push",
        "Merge Request Hook": "merge_request",
    }
    expected_kind = expected_kind_by_event.get(event_name)
    if expected_kind is not None and object_kind not in {None, expected_kind}:
        raise ValueError("GitLab webhook 이벤트 헤더와 본문 유형이 일치하지 않습니다.")
    if object_kind in set(expected_kind_by_event.values()) and expected_kind is None:
        raise ValueError("GitLab webhook 이벤트 헤더와 본문 유형이 일치하지 않습니다.")


def _read_git_head_sha(value: object) -> str | None:
    sha = _read_nullable_string(value)
    if sha is None or sha == "0" * 40:
        return None
    return sha


def _commit_shas_from_push(payload: dict[str, object]) -> tuple[str, ...]:
    commits = payload.get("commits")
    if not isinstance(commits, list):
        return ()
    shas: list[str] = []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
        commit_sha = _read_git_head_sha(commit.get("id"))
        if commit_sha is not None and commit_sha not in shas:
            shas.append(commit_sha)
    return tuple(shas)


def _commit_shas_from_merge_request(
    last_commit: dict[object, object],
) -> tuple[str, ...]:
    commit_sha = _read_git_head_sha(last_commit.get("id"))
    return () if commit_sha is None else (commit_sha,)
