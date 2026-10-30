import uuid
from datetime import UTC, datetime

from app.audit.service import _prepare, scrub


def test_sensitive_keys_dropped_at_any_depth():
    payload = {
        "email": "a@flowguard.example.org",
        "password": "plain",
        "password_hash": "$argon2id$...",
        "nested": {"refresh_token": "abc", "role": "auditor"},
        "items": [{"access_token": "t", "ok": 1}],
        "jwt_secret": "s",
    }
    assert scrub(payload) == {
        "email": "a@flowguard.example.org",
        "nested": {"role": "auditor"},
        "items": [{"ok": 1}],
    }


def test_values_made_json_safe():
    user_id = uuid.uuid4()
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    assert _prepare({"id": user_id, "at": moment}) == {
        "id": str(user_id),
        "at": "2026-01-01T00:00:00Z",
    }


def test_none_payload_kept_as_none():
    assert _prepare(None) is None
