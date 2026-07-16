"""Application configuration via environment variables.

All settings are read once at import time from the process environment (or a
``.env`` file in the project root) and validated by *pydantic-settings*.

Usage::

    from src.config import settings

    print(settings.renac_base_url)
    print(settings.shinemonitor_company_key)
    print(settings.smtp_host)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "settings"]

# Locate the project root (.env lives two directories above src/config.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Validated, typed application settings.

    All fields map 1-to-1 with the variables in ``.env.example``.
    Pydantic will raise a ``ValidationError`` at startup if any required
    variable is missing or has the wrong type.

    Tokens and session secrets are NEVER stored here — they are obtained
    and refreshed automatically by each provider client at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # RENAC Power
    # Verified base URL: https://asia.renacpower.com:8084
    # Note: RENAC_APP_KEY is intentionally absent.
    #       The sign algorithm uses MD5(email + password + timestamp)
    #       with an empty app_key — no separate key is required for this API.
    # ------------------------------------------------------------------
    renac_base_url: str = Field(
        default="https://asia.renacpower.com:8084",
        description="RENAC monitoring API base URL (verified: asia.renacpower.com:8084).",
    )
    renac_email: str = Field(
        ...,
        description="RENAC account e-mail address.",
    )
    renac_password: str = Field(
        ...,
        description="RENAC account password (plaintext; used only for sign computation).",
    )
    renac_station_id: str = Field(
        ...,
        description="Numeric identifier of the RENAC power station (e.g. 149199).",
    )

    # ------------------------------------------------------------------
    # ShineMonitor (Eybond SmartClient)
    # Verified base URL: https://web.shinemonitor.com/public/
    # Token and secret are runtime-only — never stored in config.
    # ------------------------------------------------------------------
    shinemonitor_base_url: str = Field(
        default="https://web.shinemonitor.com/public/",
        description="ShineMonitor public API base URL (verified: web.shinemonitor.com).",
    )
    shinemonitor_username: str = Field(
        ...,
        description="ShineMonitor account username / e-mail.",
    )
    shinemonitor_password: str = Field(
        ...,
        description="ShineMonitor account password (plaintext; SHA1-hashed before sending).",
    )
    shinemonitor_company_key: str = Field(
        ...,
        description="ShineMonitor company key provided by the portal (e.g. bnrl_frRFjEz8Mkn).",
    )
    shinemonitor_plant_id: str = Field(
        ...,
        description="ShineMonitor plant (station) identifier (e.g. 1301951).",
    )

    # ------------------------------------------------------------------
    # Global HTTP / runtime settings
    # ------------------------------------------------------------------
    http_timeout: int = Field(
        default=15,
        ge=1,
        le=120,
        description="HTTP request timeout in seconds.",
    )
    http_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts on transient failures.",
    )
    log_level: str = Field(
        default="INFO",
        description="Loguru log level string.",
    )
    poll_interval_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="How often (minutes) the scheduler runs a full data fetch.",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone name for display/logging (e.g. Asia/Kolkata, UTC).",
    )

    # ------------------------------------------------------------------
    # Notifications — Email (SMTP)
    # All optional; leave blank to disable email notifications.
    # ------------------------------------------------------------------
    smtp_host: Optional[str] = Field(
        default=None,
        description="SMTP server hostname. Leave blank to disable email alerts.",
    )
    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP server port (587 = STARTTLS, 465 = SSL).",
    )
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP authentication username.",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP authentication password.",
    )
    email_to: Optional[str] = Field(
        default=None,
        description="Recipient e-mail address for alert notifications.",
    )

    # ------------------------------------------------------------------
    # Notifications — Telegram
    # Leave TELEGRAM_BOT_TOKEN blank to disable.
    # ------------------------------------------------------------------
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram Bot API token. Leave blank to disable Telegram alerts.",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat or group ID to send alerts to.",
    )

    # ------------------------------------------------------------------
    # Notifications — Discord
    # Leave DISCORD_WEBHOOK_URL blank to disable.
    # ------------------------------------------------------------------
    discord_webhook_url: Optional[str] = Field(
        default=None,
        description="Discord incoming webhook URL. Leave blank to disable Discord alerts.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Normalise and validate the log level string.

        Args:
            v: Raw string from environment variable.

        Returns:
            Uppercase log level string.

        Raises:
            ValueError: If *v* is not a recognised loguru level.
        """
        allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got '{v}'")
        return upper

    @field_validator("renac_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Remove trailing slash from RENAC base URL for consistent path joining.

        ShineMonitor's base URL is NOT stripped here because it is used as the
        complete API endpoint (e.g. ``http://api.shinemonitor.com/public/``) and
        the trailing slash is required by the API.  The ShineMonitor client calls
        ``.rstrip("/")`` itself in ``__init__`` so the effective URL remains correct.

        Args:
            v: Raw URL string.

        Returns:
            URL string without trailing slash.
        """
        return v.rstrip("/")

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def email_notifications_enabled(self) -> bool:
        """Return ``True`` when SMTP is fully configured."""
        return bool(self.smtp_host and self.email_to)

    @property
    def telegram_notifications_enabled(self) -> bool:
        """Return ``True`` when Telegram is fully configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def discord_notifications_enabled(self) -> bool:
        """Return ``True`` when Discord webhook is configured."""
        return bool(self.discord_webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton :class:`Settings` instance (cached after first call).

    Returns:
        Validated ``Settings`` object.
    """
    return Settings()  # type: ignore[call-arg]


# Module-level singleton — preferred import target
settings: Settings = get_settings()


if __name__ == "__main__":
    # Quick sanity check — requires a .env file in the project root
    import json

    try:
        s = get_settings()
        print("Settings loaded successfully:")
        # Print non-sensitive fields only
        print(
            json.dumps(
                {
                    "renac_base_url": s.renac_base_url,
                    "renac_email": s.renac_email,
                    "renac_station_id": s.renac_station_id,
                    "shinemonitor_base_url": s.shinemonitor_base_url,
                    "shinemonitor_username": s.shinemonitor_username,
                    "shinemonitor_plant_id": s.shinemonitor_plant_id,
                    "shinemonitor_source": s.shinemonitor_source,
                    "shinemonitor_app_client": s.shinemonitor_app_client,
                    "shinemonitor_app_id": s.shinemonitor_app_id,
                    "shinemonitor_app_version": s.shinemonitor_app_version,
                    "http_timeout": s.http_timeout,
                    "http_max_retries": s.http_max_retries,
                    "log_level": s.log_level,
                    "poll_interval_minutes": s.poll_interval_minutes,
                    "timezone": s.timezone,
                    "email_notifications_enabled": s.email_notifications_enabled,
                    "telegram_notifications_enabled": s.telegram_notifications_enabled,
                    "discord_notifications_enabled": s.discord_notifications_enabled,
                },
                indent=2,
            )
        )
    except Exception as exc:
        print(f"Failed to load settings: {exc}")
        print("Ensure a .env file exists in the project root (copy .env.example).")
