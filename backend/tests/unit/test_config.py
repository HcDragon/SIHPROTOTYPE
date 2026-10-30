import pytest

from app.core.config import PLACEHOLDER_JWT_SECRET, ConfigurationError, load_settings

DB_URL = "postgresql+psycopg://u:p@localhost:5432/db"
GOOD_SECRET = "x" * 40


@pytest.fixture(autouse=True)
def _default_argon2_costs(monkeypatch):
    # conftest lowers Argon2 costs for speed; these tests need the production defaults.
    for name in ("ARGON2_TIME_COST", "ARGON2_MEMORY_COST", "ARGON2_PARALLELISM"):
        monkeypatch.delenv(name, raising=False)


def test_valid_settings_load():
    settings = load_settings(database_url=DB_URL, jwt_secret=GOOD_SECRET, app_env="production")
    assert settings.database_url == DB_URL
    assert settings.is_production


def test_missing_database_url_is_named(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigurationError, match="missing required setting DATABASE_URL"):
        load_settings(_env_file=None, jwt_secret=GOOD_SECRET)


def test_short_secret_rejected():
    with pytest.raises(ConfigurationError, match="at least 32 characters"):
        load_settings(database_url=DB_URL, jwt_secret="short", app_env="development")


def test_placeholder_secret_rejected_in_production():
    with pytest.raises(ConfigurationError, match="must be changed"):
        load_settings(database_url=DB_URL, jwt_secret=PLACEHOLDER_JWT_SECRET, app_env="production")


@pytest.mark.parametrize("env", ["development", "test"])
def test_placeholder_secret_allowed_in_development_and_test(env):
    settings = load_settings(database_url=DB_URL, jwt_secret=PLACEHOLDER_JWT_SECRET, app_env=env)
    assert settings.jwt_secret == PLACEHOLDER_JWT_SECRET


@pytest.mark.parametrize("env", ["development", "production"])
def test_reduced_argon2_cost_only_in_test(env):
    with pytest.raises(ConfigurationError, match="Reduced Argon2"):
        load_settings(
            database_url=DB_URL, jwt_secret=GOOD_SECRET, app_env=env, argon2_memory_cost=1024
        )


def test_reduced_argon2_cost_allowed_in_test():
    settings = load_settings(
        database_url=DB_URL, jwt_secret=GOOD_SECRET, app_env="test", argon2_memory_cost=1024
    )
    assert settings.argon2_memory_cost == 1024


def test_cors_origins_parsed():
    settings = load_settings(
        database_url=DB_URL, jwt_secret=GOOD_SECRET, cors_origins="http://a, http://b"
    )
    assert settings.cors_origin_list == ["http://a", "http://b"]
