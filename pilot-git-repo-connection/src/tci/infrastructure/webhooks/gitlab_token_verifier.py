from __future__ import annotations

from dataclasses import dataclass
import hmac
import uuid


@dataclass(frozen=True, slots=True)
class GitLabTokenCandidate:
    revision_id: uuid.UUID
    secret: str
    status: str


@dataclass(frozen=True, slots=True)
class GitLabTokenVerificationInput:
    token_header: str | None
    candidates: tuple[GitLabTokenCandidate, ...] = ()
    active_secret: str | None = None
    active_secret_revision_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class GitLabTokenVerificationOutcome:
    signature_status: str
    verified_secret_revision_id: uuid.UUID | None
    verified_secret_revision_status: str | None

    @property
    def is_verified(self) -> bool:
        return self.signature_status == "verified"

    @property
    def rejection_reason(self) -> str | None:
        if self.is_verified:
            return None
        return self.signature_status


def evaluate_gitlab_token_verification(
    verification_input: GitLabTokenVerificationInput,
) -> GitLabTokenVerificationOutcome:
    candidates = _verification_candidates(verification_input)
    if not candidates:
        return GitLabTokenVerificationOutcome(
            signature_status="secret_missing",
            verified_secret_revision_id=None,
            verified_secret_revision_status=None,
        )
    if verification_input.token_header is None:
        return GitLabTokenVerificationOutcome(
            signature_status="secret_mismatch",
            verified_secret_revision_id=None,
            verified_secret_revision_status=None,
        )
    for candidate in candidates:
        if hmac.compare_digest(candidate.secret, verification_input.token_header):
            return GitLabTokenVerificationOutcome(
                signature_status="verified",
                verified_secret_revision_id=candidate.revision_id,
                verified_secret_revision_status=candidate.status,
            )
    return GitLabTokenVerificationOutcome(
        signature_status="secret_mismatch",
        verified_secret_revision_id=None,
        verified_secret_revision_status=None,
    )


def _verification_candidates(
    verification_input: GitLabTokenVerificationInput,
) -> tuple[GitLabTokenCandidate, ...]:
    if verification_input.candidates:
        return verification_input.candidates
    if (
        verification_input.active_secret is not None
        and verification_input.active_secret_revision_id is not None
    ):
        return (
            GitLabTokenCandidate(
                revision_id=verification_input.active_secret_revision_id,
                secret=verification_input.active_secret,
                status="active",
            ),
        )
    return ()
