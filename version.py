"""Backward-compatible shim for legacy imports.

Prefer importing from app_version to avoid collisions with third-party modules named
`version` in frozen builds.
"""

from app_version import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION"]
