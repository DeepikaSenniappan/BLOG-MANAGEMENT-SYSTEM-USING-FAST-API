"""Environment-backed application settings."""

import os
from dataclasses import dataclass


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from: str
    smtp_use_ssl: bool
    smtp_use_starttls: bool


def get_email_settings() -> EmailSettings:
    """Read SMTP configuration when a notification is sent."""
    username = _optional_env("SMTP_USERNAME")
    return EmailSettings(
        smtp_host=_optional_env("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=username,
        smtp_password=_optional_env("SMTP_PASSWORD"),
        smtp_from=_optional_env("SMTP_FROM") or username or "blog@example.com",
        smtp_use_ssl=os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"},
        smtp_use_starttls=os.getenv("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"},
    )
