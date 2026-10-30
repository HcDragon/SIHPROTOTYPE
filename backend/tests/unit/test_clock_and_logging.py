import logging
from datetime import UTC, datetime, timedelta, timezone

from app.core.clock import frozen_time, utcnow
from app.core.logging import REDACTED, RedactingFilter, redact, redact_text
from app.core.schemas import ResponseModel, UtcDatetime


class Stamped(ResponseModel):
    at: UtcDatetime


def test_utcnow_is_aware_utc():
    assert utcnow().tzinfo is UTC


def test_frozen_time():
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    with frozen_time(moment):
        assert utcnow() == moment
    assert utcnow() != moment


def test_timestamps_serialize_in_utc_with_offset():
    ist = timezone(timedelta(hours=5, minutes=30))
    value = Stamped(at=datetime(2026, 1, 1, 10, 0, tzinfo=ist)).model_dump_json()
    assert '"2026-01-01T04:30:00Z"' in value


def test_naive_timestamp_treated_as_utc():
    assert Stamped(at=datetime(2026, 1, 1, 10, 0)).at.tzinfo is UTC


def test_redact_nested_keys():
    data = {"email": "a@example.org", "password": "x", "nested": [{"refresh_token": "y"}]}
    assert redact(data) == {
        "email": "a@example.org",
        "password": REDACTED,
        "nested": [{"refresh_token": REDACTED}],
    }


def test_redact_inline_text():
    assert redact_text("login password=hunter2 ok") == f"login password={REDACTED} ok"
    assert "abc.def" not in redact_text("Authorization: abc.def")


def test_filter_redacts_args_and_extras():
    record = logging.makeLogRecord(
        {"msg": "payload %s", "args": ({"jwt_secret": "s", "role": "auditor"},)}
    )
    record.access_token = "tok"
    RedactingFilter().filter(record)
    assert record.getMessage() == f"payload {{'jwt_secret': '{REDACTED}', 'role': 'auditor'}}"
    assert record.access_token == REDACTED
