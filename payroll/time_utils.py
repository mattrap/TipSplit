"""Timezone and datetime helpers for payroll calculations."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Optional, Union

try:  # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover - fallback handled below
    ZoneInfo = None  # type: ignore

try:
    import pytz  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytz = None  # type: ignore

LocalTZ = Union[str, "ZoneInfo", "pytz.BaseTzInfo"]


class TimezoneError(RuntimeError):
    """Raised when timezone data cannot be resolved."""


def _normalize_tz(tz: LocalTZ):
    if isinstance(tz, str):
        return get_timezone(tz)
    return tz


@lru_cache(maxsize=32)
def get_timezone(name: str):
    """Return a tzinfo for the given name using zoneinfo or pytz."""
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception as exc:  # pragma: no cover - zoneinfo errors rare
            if pytz is None:
                raise TimezoneError(f"Timezone '{name}' introuvable: {exc}") from exc
    if pytz is not None:
        try:
            return pytz.timezone(name)
        except Exception as exc:  # pragma: no cover
            raise TimezoneError(f"Timezone '{name}' introuvable: {exc}") from exc
    raise TimezoneError("Aucune bibliothèque timezone disponible. Installez 'tzdata' ou 'pytz'.")


def parse_local_iso(dt_str: str, tz: LocalTZ) -> datetime:
    """Parse a local ISO datetime string and attach the provided timezone."""
    tzinfo = _normalize_tz(tz)
    naive = datetime.fromisoformat(dt_str)
    if getattr(tzinfo, "localize", None):  # pytz
        return tzinfo.localize(naive)
    return naive.replace(tzinfo=tzinfo)


def ensure_local(dt_value: Union[datetime, date], tz: LocalTZ) -> datetime:
    tzinfo = _normalize_tz(tz)
    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is None:
            if getattr(tzinfo, "localize", None):
                return tzinfo.localize(dt_value)
            return dt_value.replace(tzinfo=tzinfo)
        return dt_value.astimezone(tzinfo)
    return datetime.combine(dt_value, time.min, tzinfo)


def to_utc_iso(dt_value: datetime) -> str:
    """Convert an aware datetime to a canonical UTC ISO string."""
    if dt_value.tzinfo is None:
        raise ValueError("Datetime doit être aware pour conversion UTC.")
    as_utc = dt_value.astimezone(timezone.utc)
    return as_utc.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def from_utc_iso(value: str) -> datetime:
    """Parse an ISO string (with optional trailing 'Z') into UTC aware datetime."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt_value = datetime.fromisoformat(normalized)
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def to_local(dt_utc: datetime, tz: LocalTZ) -> datetime:
    tzinfo = _normalize_tz(tz)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(tzinfo)


def date_in_local(dt_utc: datetime, tz: LocalTZ) -> date:
    return to_local(dt_utc, tz).date()


def normalize_date(value: Union[str, date, datetime]) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise TypeError(f"Type non supporté pour date: {type(value)!r}")
