from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit


_URL_PATTERN = re.compile(r"\b(?:https?|ssh)://\S+")
_SCP_REMOTE_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+:[^\s]+")
_RUNTIME_PATH_PATTERN = re.compile(r"\.runtime/[^\s'\"),;]+")
_QUOTED_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:'[^'\r\n]*(?:/|[A-Za-z]:\\)[^'\r\n]*'|"
    r'"[^"\r\n]*(?:/|[A-Za-z]:\\)[^"\r\n]*")'
)
_SPACE_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:/[^\r\n'\";,]+|[A-Za-z]:\\[^\r\n'\";,]+)"
)
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:/[^\s]+|[A-Za-z]:\\[^\s]+)")
_SECRET_HEADER_PATTERN = re.compile(r"\bAuthorization\s*:\s*[^\r\n]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b[A-Za-z0-9_-]*(?:token|secret|password|credential|key)[A-Za-z0-9_-]*"
    r"\s*(?:=|:)\s*[^\s]+",
    re.IGNORECASE,
)
_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]+")


def bounded_failure_message(message: str | None, *, limit: int = 512) -> str | None:
    if message is None:
        return None
    sanitized = _URL_PATTERN.sub("[redacted-url]", message[: limit * 4])
    sanitized = _SCP_REMOTE_PATTERN.sub("[redacted-url]", sanitized)
    sanitized = unquote(sanitized)
    sanitized = _URL_PATTERN.sub("[redacted-url]", sanitized)
    sanitized = _SCP_REMOTE_PATTERN.sub("[redacted-url]", sanitized)
    sanitized = _RUNTIME_PATH_PATTERN.sub(" [redacted-path]", sanitized)
    sanitized = _QUOTED_ABSOLUTE_PATH_PATTERN.sub("[redacted-path]", sanitized)
    sanitized = _SPACE_ABSOLUTE_PATH_PATTERN.sub("[redacted-path]", sanitized)
    sanitized = _ABSOLUTE_PATH_PATTERN.sub("[redacted-path]", sanitized)
    sanitized = _SECRET_HEADER_PATTERN.sub("[redacted-secret]", sanitized)
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub("[redacted-secret]", sanitized)
    sanitized = _CONTROL_PATTERN.sub(" ", sanitized)
    return " ".join(sanitized.split())[:limit]


def bounded_display_filename(filename: str, *, limit: int = 255) -> str:
    sanitized = _CONTROL_PATTERN.sub(" ", unquote(filename[: limit * 4]))
    parsed = urlsplit(sanitized)
    if parsed.scheme or parsed.netloc:
        sanitized = parsed.path or "upload.zip"
    sanitized = re.split(r"[?#]", sanitized, maxsplit=1)[0].strip()
    sanitized = re.split(r"[\\/]", sanitized)[-1].strip(" \t'\"")
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub("", sanitized).strip()
    sanitized = re.sub(r"[^A-Za-z0-9._ -]+", "_", sanitized).strip(" ._")
    if not sanitized:
        sanitized = "upload.zip"
    return sanitized[:limit]
