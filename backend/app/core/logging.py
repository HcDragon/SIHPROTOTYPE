"""Logging setup with redaction of sensitive values."""

import logging
import re
from typing import Any

SENSITIVE_KEY = re.compile(r"password|token|secret|authorization|hash", re.IGNORECASE)
REDACTED = "[REDACTED]"
_INLINE_SECRET = re.compile(
    r"(?P<key>\b\w*(?:password|token|secret|authorization)\w*\b)(?P<sep>\s*[=:]\s*)(?P<value>\S+)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    return bool(SENSITIVE_KEY.search(key))


def redact(value: Any) -> Any:
    """Return a copy with values under sensitive keys replaced."""
    if isinstance(value, dict):
        return {k: REDACTED if is_sensitive_key(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(redact(v) for v in value)
    return value


def redact_text(text: str) -> str:
    return _INLINE_SECRET.sub(lambda m: f"{m['key']}{m['sep']}{REDACTED}", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact(arg) for arg in record.args)
        record.msg = redact_text(str(record.msg))
        for key in list(vars(record)):
            if is_sensitive_key(key) and key not in _STANDARD_RECORD_KEYS:
                setattr(record, key, REDACTED)
        return True


_STANDARD_RECORD_KEYS = set(vars(logging.makeLogRecord({})))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
