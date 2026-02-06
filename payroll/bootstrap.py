"""Bootstrap helpers for payroll tables."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from db.db_manager import db_session
from payroll.pay_calendar import PayCalendarService
from payroll.time_utils import get_timezone

DEFAULT_TZ = "America/Montreal"


def ensure_default_schedule(group_key: str = "default") -> Optional[dict]:
    """Ensure a schedule exists; return the active schedule."""
    service = PayCalendarService(default_group=group_key)
    with db_session() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM pay_schedules WHERE group_key = ?",
            (group_key,),
        ).fetchone()
        if row and row["total"]:
            return service.get_active_schedule(group_key=group_key)

    tzinfo = get_timezone(DEFAULT_TZ)
    now_local = datetime.now(tzinfo)
    days_since_sunday = (now_local.weekday() - 6) % 7
    anchor_date = (now_local - timedelta(days=days_since_sunday)).date()
    anchor_dt = datetime.combine(anchor_date, time(hour=6, minute=0))
    anchor_local_str = anchor_dt.isoformat(timespec="seconds")
    today_local = now_local.date()

    schedule = service.create_schedule_version(
        name="Horaire par défaut",
        timezone_name=DEFAULT_TZ,
        period_length_days=14,
        pay_date_offset_days=4,
        anchor_start_local=anchor_local_str,
        effective_from=anchor_date,
        group_key=group_key,
    )

    service.ensure_periods(
        schedule["id"],
        today_local - timedelta(days=180),
        today_local + timedelta(days=365),
    )
    return schedule
