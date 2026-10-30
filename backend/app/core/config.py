"""Environment-based settings. All configuration comes from environment variables or `.env`."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDER_JWT_SECRET = "change-me-to-a-random-string-of-at-least-32-characters"  # noqa: S105 (documented placeholder, rejected outside dev/test)
MIN_JWT_SECRET_LENGTH = 32

# argon2-cffi defaults (RFC 9106 low-memory profile). Lower values are allowed only in tests.
ARGON2_DEFAULT_TIME_COST = 3
ARGON2_DEFAULT_MEMORY_COST = 65536
ARGON2_DEFAULT_PARALLELISM = 4


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ConfigurationError(RuntimeError):
    """Raised at startup when configuration is missing or unsafe."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Environment = Environment.DEVELOPMENT
    database_url: str
    jwt_secret: str
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=90)
    demo_password: str = "change-me-demo-password"  # noqa: S105 (development default)
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    argon2_time_cost: int = Field(default=ARGON2_DEFAULT_TIME_COST, ge=1)
    argon2_memory_cost: int = Field(default=ARGON2_DEFAULT_MEMORY_COST, ge=8)
    argon2_parallelism: int = Field(default=ARGON2_DEFAULT_PARALLELISM, ge=1)

    @model_validator(mode="after")
    def _check_safety(self) -> "Settings":
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long")
        relaxed = self.app_env in (Environment.DEVELOPMENT, Environment.TEST)
        if not relaxed and self.jwt_secret == PLACEHOLDER_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be changed from the .env.example placeholder "
                f"when APP_ENV is {self.app_env.value}"
            )
        reduced_argon2 = (
            self.argon2_time_cost < ARGON2_DEFAULT_TIME_COST
            or self.argon2_memory_cost < ARGON2_DEFAULT_MEMORY_COST
            or self.argon2_parallelism < ARGON2_DEFAULT_PARALLELISM
        )
        if reduced_argon2 and self.app_env is not Environment.TEST:
            raise ValueError("Reduced Argon2 cost settings are only allowed when APP_ENV is test")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION


def load_settings(**overrides: object) -> Settings:
    """Build settings, turning validation problems into a readable startup error."""
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"]).upper()
            if error["type"] == "missing":
                problems.append(f"missing required setting {field}")
            elif field:
                problems.append(f"{field}: {error['msg']}")
            else:
                problems.append(error["msg"].removeprefix("Value error, "))
        raise ConfigurationError("Invalid configuration: " + "; ".join(problems)) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
