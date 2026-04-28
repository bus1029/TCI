from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import uuid


@dataclass(frozen=True, slots=True)
class GitHubSignatureVerificationResult:
    matched_revision_id: uuid.UUID | None
    matched_revision_status: str | None
    signature_is_valid: bool


def verify_github_webhook_signature(
    *,
    secret_candidates,
    signature_header: str | None,
    raw_body: bytes,
) -> GitHubSignatureVerificationResult:
    if signature_header is None or not signature_header.startswith("sha256="):
        return GitHubSignatureVerificationResult(
            matched_revision_id=None,
            matched_revision_status=None,
            signature_is_valid=False,
        )
    provided_digest = signature_header.removeprefix("sha256=")
    if len(provided_digest) != 64 or not _is_hex_digest(provided_digest):
        return GitHubSignatureVerificationResult(
            matched_revision_id=None,
            matched_revision_status=None,
            signature_is_valid=False,
        )
    for candidate in secret_candidates:
        secret = getattr(candidate, "secret", None)
        if secret is None:
            secret = getattr(candidate, "encrypted_secret", "")
        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(digest, provided_digest):
            return GitHubSignatureVerificationResult(
                matched_revision_id=getattr(candidate, "revision_id", None)
                or getattr(candidate, "id", None),
                matched_revision_status=getattr(candidate, "status", None)
                if isinstance(getattr(candidate, "status", None), str)
                else getattr(getattr(candidate, "status", None), "value", None),
                signature_is_valid=True,
            )
    return GitHubSignatureVerificationResult(
        matched_revision_id=None,
        matched_revision_status=None,
        signature_is_valid=False,
    )


def _is_hex_digest(value: str) -> bool:
    return all(character in "0123456789abcdef" for character in value)
