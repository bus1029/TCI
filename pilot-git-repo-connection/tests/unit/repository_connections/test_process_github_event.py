from __future__ import annotations

from tci.domain.services.process_github_event import (
    GitHubDecisionInput,
    SecretVerificationInput,
    decide_github_event_processing,
    evaluate_github_secret_verification,
)


def test_evaluate_github_secret_verification_classifies_missing_mismatch_and_invalid() -> None:
    assert evaluate_github_secret_verification(
        SecretVerificationInput(
            has_any_secret=False,
            matched_secret_status=None,
            signature_header="sha256=abc123",
            signature_is_valid=False,
        )
    ).signature_status == "secret_missing"
    assert evaluate_github_secret_verification(
        SecretVerificationInput(
            has_any_secret=True,
            matched_secret_status=None,
            signature_header="sha256=abc123",
            signature_is_valid=False,
        )
    ).signature_status == "secret_mismatch"
    assert evaluate_github_secret_verification(
        SecretVerificationInput(
            has_any_secret=True,
            matched_secret_status=None,
            signature_header="sha256=not-a-valid-hex",
            signature_is_valid=False,
        )
    ).signature_status == "signature_invalid"


def test_process_github_event_accepts_previous_grace_secret_and_marks_revision_status() -> None:
    outcome = evaluate_github_secret_verification(
        SecretVerificationInput(
            has_any_secret=True,
            matched_secret_status="previous_grace",
            signature_header="sha256=abc123",
            signature_is_valid=True,
        )
    )

    assert outcome.signature_status == "verified"
    assert outcome.verified_secret_revision_status == "previous_grace"


def test_process_github_event_records_ignored_pr_action_without_queueing_sync() -> None:
    decision = decide_github_event_processing(
        GitHubDecisionInput(
            provider_event_type="pull_request",
            provider_action="closed",
            target_head_sha="a" * 40,
            delivery_already_seen=False,
            latest_cursor_head_sha=None,
            resolved_current_head_sha="a" * 40,
        )
    )

    assert decision.processing_decision == "record_only"
    assert decision.should_queue_sync is False


def test_process_github_event_marks_duplicate_delivery_duplicate_head_and_stale_head() -> None:
    duplicate_delivery = decide_github_event_processing(
        GitHubDecisionInput(
            provider_event_type="push",
            provider_action=None,
            target_head_sha="a" * 40,
            delivery_already_seen=True,
            latest_cursor_head_sha=None,
            resolved_current_head_sha="a" * 40,
        )
    )
    duplicate_head = decide_github_event_processing(
        GitHubDecisionInput(
            provider_event_type="push",
            provider_action=None,
            target_head_sha="b" * 40,
            delivery_already_seen=False,
            latest_cursor_head_sha="b" * 40,
            resolved_current_head_sha="b" * 40,
        )
    )
    stale_head = decide_github_event_processing(
        GitHubDecisionInput(
            provider_event_type="push",
            provider_action=None,
            target_head_sha="c" * 40,
            delivery_already_seen=False,
            latest_cursor_head_sha="d" * 40,
            resolved_current_head_sha="d" * 40,
        )
    )

    assert duplicate_delivery.processing_decision == "duplicate_delivery"
    assert duplicate_delivery.should_queue_sync is False
    assert duplicate_head.processing_decision == "duplicate_head"
    assert duplicate_head.should_queue_sync is False
    assert stale_head.processing_decision == "stale_head"
    assert stale_head.should_queue_sync is False
