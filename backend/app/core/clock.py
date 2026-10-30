"""Single source of "now" so tests can freeze time."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime


def _system_now() -> datetime:
    return datetime.now(UTC)


_now: Callable[[], datetime] = _system_now


def utcnow() -> datetime:
    return _now()


@contextmanager
def frozen_time(at: datetime) -> Iterator[None]:
    global _now
    previous = _now
    _now = lambda: at  # noqa: E731
    try:
        yield
    finally:
        _now = previous
