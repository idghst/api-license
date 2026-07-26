from functools import lru_cache
from typing import Annotated, ClassVar, Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _require_http_origin(value: object, *, allow_root_path: bool) -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError("must be a concrete HTTP(S) origin")

    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("must use a valid port") from error

    valid_path = not parsed.path or (allow_root_path and parsed.path == "/")
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        and not 0 < port <= 65535
        or not valid_path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("must be a concrete HTTP(S) origin")
    return value


class Settings(BaseSettings):
    """Validated runtime configuration loaded from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    ENABLE_DOCS: bool | None = None
    CORS_ORIGINS: list[str] = []
    SUPABASE_URL: AnyHttpUrl
    SUPABASE_PUBLISHABLE_KEY: SecretStr
    SUPABASE_SECRET_KEY: SecretStr | None = None
    SUPABASE_TIMEOUT_SECONDS: Annotated[float, Field(gt=0)] = 5.0

    app_name: ClassVar[str] = "License API"
    supabase_schema: ClassVar[str] = "license"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def require_concrete_cors_origins(cls, values: list[str]) -> list[str]:
        return [_require_http_origin(value, allow_root_path=False) for value in values]

    @field_validator("SUPABASE_URL", mode="before")
    @classmethod
    def require_supabase_origin(cls, value: object) -> object:
        return _require_http_origin(value, allow_root_path=True)

    @field_validator("SUPABASE_URL")
    @classmethod
    def require_https_supabase_in_production(
        cls, value: AnyHttpUrl, info: ValidationInfo
    ) -> AnyHttpUrl:
        if info.data.get("APP_ENV") == "production" and value.scheme != "https":
            raise ValueError("SUPABASE_URL must use HTTPS in production")
        return value

    @field_validator("SUPABASE_PUBLISHABLE_KEY", mode="before")
    @classmethod
    def require_nonblank_publishable_key(cls, value: object) -> object:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must not be blank")
        return value

    @field_validator("SUPABASE_SECRET_KEY", mode="before")
    @classmethod
    def normalize_blank_secret_key(cls, value: object) -> object:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return value

    @property
    def docs_enabled(self) -> bool:
        return (
            self.ENABLE_DOCS
            if self.ENABLE_DOCS is not None
            else self.APP_ENV != "production"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Loaded from the environment.


def clear_settings_cache() -> None:
    get_settings.cache_clear()
