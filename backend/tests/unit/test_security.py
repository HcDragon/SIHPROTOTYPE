import base64
import json
import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.clock import utcnow
from app.core.config import load_settings
from app.core.errors import InvalidToken
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

USER_ID = uuid.uuid4()


def test_password_hash_is_argon2id_and_not_plaintext(settings):
    hashed = hash_password("s3cret-pass-phrase", settings)
    assert hashed.startswith("$argon2id$")
    assert "s3cret-pass-phrase" not in hashed


def test_password_hashes_are_salted(settings):
    assert hash_password("same", settings) != hash_password("same", settings)


def test_verify_password(settings):
    hashed = hash_password("right", settings)
    assert verify_password(hashed, "right", settings)
    assert not verify_password(hashed, "wrong", settings)
    assert not verify_password("not-a-hash", "right", settings)


def test_valid_token_round_trip(settings):
    token, expires_in = create_access_token(USER_ID, "auditor", settings)
    claims = decode_access_token(token, settings)
    assert claims.user_id == USER_ID
    assert claims.role == "auditor"
    assert expires_in == settings.access_token_ttl_minutes * 60


def test_expired_token_rejected(settings):
    past = utcnow() - timedelta(minutes=settings.access_token_ttl_minutes + 1)
    token, _ = create_access_token(USER_ID, "auditor", settings, now=past)
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


def _tamper_payload(token: str, **changes) -> str:
    header, payload, signature = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data.update(changes)
    new_payload = base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
    return f"{header}.{new_payload}.{signature}"


def test_tampered_payload_rejected(settings):
    token, _ = create_access_token(USER_ID, "auditor", settings)
    with pytest.raises(InvalidToken):
        decode_access_token(_tamper_payload(token, role="super_admin"), settings)


def test_tampered_signature_rejected(settings):
    token, _ = create_access_token(USER_ID, "auditor", settings)
    head, _, sig = token.rpartition(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(InvalidToken):
        decode_access_token(f"{head}.{flipped}", settings)


def test_token_signed_with_other_secret_rejected(settings):
    other = load_settings(
        database_url=settings.database_url, jwt_secret="another-secret-" + "y" * 32, app_env="test"
    )
    token, _ = create_access_token(USER_ID, "auditor", other)
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


@pytest.mark.parametrize("algorithm", ["HS512", "none"])
def test_other_algorithms_rejected(settings, algorithm):
    now = utcnow()
    payload = {
        "sub": str(USER_ID),
        "role": "auditor",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": "x",
        "typ": "access",
    }
    key = settings.jwt_secret if algorithm != "none" else None
    token = jwt.encode(payload, key, algorithm=algorithm)
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


def test_missing_claim_rejected(settings):
    now = utcnow()
    token = jwt.encode(
        {"sub": str(USER_ID), "exp": now + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, settings)


@pytest.mark.parametrize("value", ["", "garbage", "a.b.c", "Bearer xyz"])
def test_malformed_token_rejected(settings, value):
    with pytest.raises(InvalidToken):
        decode_access_token(value, settings)


def test_refresh_token_values_and_hash():
    raw, digest = new_refresh_token()
    assert len(raw) >= 43
    assert digest == hash_refresh_token(raw)
    assert len(digest) == 64 and raw not in digest
