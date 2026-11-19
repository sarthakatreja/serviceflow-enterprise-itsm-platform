from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SERVICEFLOW_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./serviceflow.db"
    allowed_origins: str = (
        "http://127.0.0.1:5173,http://localhost:5173,"
        "http://127.0.0.1:8011,http://localhost:8011"
    )
    session_hours: int = Field(default=8, ge=1, le=72)
    cookie_secure: bool = False
    frontend_dir: Path | None = None

    @field_validator("allowed_origins")
    @classmethod
    def check_origins(cls, value: str) -> str:
        entries = [origin.strip() for origin in value.split(",") if origin.strip()]
        for origin in entries:
            parts = urlsplit(origin)
            if (
                parts.scheme not in ("http", "https")
                or not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
                or "*" in origin
                or any(character.isspace() for character in origin)
            ):
                raise ValueError("Use explicit HTTP origins without paths or wildcards.")
        return ",".join(entries)

    @property
    def origins(self) -> list[str]:
        return self.allowed_origins.split(",") if self.allowed_origins else []
