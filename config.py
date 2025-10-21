"""Application configuration loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from dotenv import load_dotenv


REQUIRED_ENV_VARS: Final[tuple[str, ...]] = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
)


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the desktop client."""

    supabase_url: str
    supabase_anon_key: str
    app_name: str = "TipSplit Desktop"


class ConfigError(RuntimeError):
    """Raised when mandatory configuration is missing."""


def load_config() -> AppConfig:
    """Load the application configuration from the environment.

    The function reads values from a local `.env` file if present and then
    validates that required keys are available. Optional keys fall back to
    sensible defaults.
    """

    load_dotenv()

    missing: list[str] = []
    values: dict[str, str] = {}

    for key in REQUIRED_ENV_VARS:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        else:
            values[key] = value

    if missing:
        raise ConfigError(
            "Missing required environment variables: " + ", ".join(sorted(missing))
        )

    app_name = os.getenv("APP_NAME", "TipSplit Desktop")

    return AppConfig(
        supabase_url=values["SUPABASE_URL"].rstrip("/"),
        supabase_anon_key=values["SUPABASE_ANON_KEY"],
        app_name=app_name,
    )


__all__ = ["AppConfig", "ConfigError", "load_config"]
