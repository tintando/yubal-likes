"""Application settings using pydantic-settings."""

import tempfile
from datetime import tzinfo
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from croniter import croniter
from pydantic import BeforeValidator, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from yubal import AudioCodec

LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    BeforeValidator(lambda v: v.upper() if isinstance(v, str) else v),
]


def _validate_timezone(v: str) -> str:
    """Validate timezone string by attempting to create ZoneInfo."""
    if isinstance(v, str):
        try:
            ZoneInfo(v)
        except KeyError as e:
            raise ValueError(f"Invalid timezone: {v}") from e
    return v


Timezone = Annotated[str, BeforeValidator(_validate_timezone)]


def _validate_cron_expression(v: str) -> str:
    """Validate cron expression using croniter."""
    if isinstance(v, str):
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")
    return v


CronExpression = Annotated[str, BeforeValidator(_validate_cron_expression)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YUBAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project root (required, set via YUBAL_ROOT)
    root: Path = Field(description="Project root directory")

    # Path settings (default to root-relative paths)
    data: Path = Field(description="Music library")
    config: Path = Field(description="Config directory")

    # Server settings
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=False, description="Enable auto-reload")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: LogLevel = Field(default="INFO", description="Log level")

    # Audio settings
    audio_format: AudioCodec = Field(
        default=AudioCodec.OPUS, description="Audio format"
    )
    audio_quality: str = Field(default="0", description="Audio quality (0 = best)")

    # Lyrics settings
    fetch_lyrics: bool = Field(default=True, description="Fetch lyrics from lrclib.net")

    # Filename settings
    ascii_filenames: bool = Field(
        default=False, description="Transliterate unicode to ASCII in filenames"
    )

    # UGC settings
    download_ugc: bool = Field(
        default=False,
        description="Download user-generated content tracks to _Unofficial",
    )

    # ReplayGain settings
    replaygain: bool = Field(
        default=True,
        description="Apply ReplayGain tags using rsgain",
    )

    # Temp directory
    temp: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "yubal",
        description="Temp directory for downloads",
    )

    # CORS settings
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")

    # Scheduler settings
    scheduler_enabled: bool = Field(
        default=True, description="Enable automatic scheduled sync"
    )
    scheduler_cron: CronExpression = Field(
        default="0 0 * * *",
        description="Cron expression for scheduled sync",
    )

    # Job execution
    job_timeout_seconds: int = Field(
        default=1800,
        ge=60,
        description="Job execution timeout in seconds",
    )

    # Timezone
    tz: Timezone = Field(default="UTC", description="Timezone for timestamps")

    # Google Drive sync
    gdrive_enabled: bool = Field(
        default=False, description="Enable Google Drive sync after download"
    )
    gdrive_folder_id: str = Field(
        default="", description="Root Drive folder ID to sync into"
    )
    gdrive_client_secrets_file: Path = Field(
        default=Path(""), description="Path to OAuth2 client secrets JSON"
    )
    gdrive_token_file: Path = Field(
        default=Path(""), description="Path to OAuth2 token JSON"
    )

    @model_validator(mode="before")
    @classmethod
    def set_path_defaults(cls, data: Any) -> Any:
        """Set path defaults based on root before validation."""
        if not isinstance(data, dict):
            return data
        root = data.get("root")
        if not root:
            raise ValueError("YUBAL_ROOT environment variable is required")
        root = Path(root) if isinstance(root, str) else root
        if not data.get("data"):
            data["data"] = root / "data"
        if not data.get("config"):
            data["config"] = root / "config"
        config = data.get("config", root / "config")
        config = Path(config) if isinstance(config, str) else config
        if not data.get("gdrive_client_secrets_file"):
            data["gdrive_client_secrets_file"] = config / "yubal" / "gdrive_client_secrets.json"
        if not data.get("gdrive_token_file"):
            data["gdrive_token_file"] = config / "yubal" / "gdrive_token.json"
        return data

    @property
    def timezone(self) -> tzinfo:
        return ZoneInfo(self.tz)

    @property
    def ytdlp_dir(self) -> Path:
        return self.config / "ytdlp"

    @property
    def cookies_file(self) -> Path:
        return self.ytdlp_dir / "cookies.txt"

    @property
    def authuser_file(self) -> Path:
        """File storing the selected x-goog-authuser index for cookies.txt."""
        return self.ytdlp_dir / "authuser.txt"

    def get_authuser(self) -> str:
        """Read the selected Google account index. Defaults to "0"."""
        try:
            value = self.authuser_file.read_text().strip()
        except (OSError, UnicodeDecodeError):
            return "0"
        # The value goes into the x-goog-authuser header; never pass through
        # anything that isn't a plain non-negative integer.
        if not (value.isascii() and value.isdigit()):
            return "0"
        return value

    @property
    def db_path(self) -> Path:
        return self.config / "yubal" / "yubal.db"

    @property
    def cache_path(self) -> Path:
        """Directory for extraction cache (same as db_path parent)."""
        return self.db_path.parent

    @property
    def thumbnails_path(self) -> Path:
        """Directory for cached album art thumbnails."""
        return self.cache_path / "thumbnails"

    @property
    def gdrive_client_configured(self) -> bool:
        """Client secrets uploaded (may still need authorization)."""
        return self.gdrive_enabled and bool(self.gdrive_folder_id) and self.gdrive_client_secrets_file.exists()

    @property
    def gdrive_authorized(self) -> bool:
        """Fully authorized (can upload to Drive)."""
        return self.gdrive_client_configured and self.gdrive_token_file.exists()

    @property
    def gdrive_configured(self) -> bool:
        return self.gdrive_authorized


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
