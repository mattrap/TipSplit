"""High level helpers around the pay calendar service."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional

from payroll.pay_calendar import PayCalendarError, PayCalendarService
from payroll.time_utils import ensure_local, from_utc_iso, get_timezone, to_local
from db.distributions_repo import list_period_ids_with_distributions_for_periods


class PayrollContext:
    """Cache the active schedule and expose convenience helpers."""

    def __init__(self, service: PayCalendarService, group_key: str = "default") -> None:
        self.service = service
        self.group_key = (group_key or "default").strip() or "default"
        self._schedule: Optional[Dict] = None
        self._tzinfo = None

    # ------------------------------------------------------------------
    # Schedule + timezone helpers
    # ------------------------------------------------------------------
    def refresh_schedule(self, for_date: Optional[date] = None) -> Dict:
        schedule = self.service.get_active_schedule(
            group_key=self.group_key,
            for_date_local=for_date,
        )
        return self.set_schedule(schedule)

    def set_schedule(self, schedule: Dict) -> Dict:
        self._schedule = schedule
        self._tzinfo = get_timezone(schedule["timezone"])
        return schedule

    def get_schedule(self) -> Dict:
        if self._schedule is None:
            return self.refresh_schedule()
        return self._schedule

    @property
    def timezone(self):  # pragma: no cover - thin helper
        self.get_schedule()
        return self._tzinfo

    # ------------------------------------------------------------------
    # Period helpers
    # ------------------------------------------------------------------
    def ensure_window(self, months_back: int = 6, months_forward: int = 12) -> None:
        schedule = self.get_schedule()
        today = date.today()
        start = today - timedelta(days=30 * months_back)
        end = today + timedelta(days=30 * months_forward)
        self.service.ensure_periods(schedule["id"], start, end)

    def list_periods(self, limit: int = 200, offset: int = 0) -> List[Dict]:
        schedule = self.get_schedule()
        rows = self.service.list_periods(schedule["id"], limit=limit, offset=offset)
        period_ids = [row.get("id") for row in rows if row.get("id")]
        periods_with_data = set(list_period_ids_with_distributions_for_periods(period_ids))
        formatted = []
        for row in rows:
            period = self._format_period(schedule, row)
            has_data = period.get("id") in periods_with_data
            period["has_data"] = has_data
            if period.get("status") == "OPEN" and not has_data:
                period["status_display"] = "EMPTY"
            else:
                period["status_display"] = period.get("status")
            formatted.append(period)
        return formatted

    def period_for_local_date(self, local_date: date) -> Dict:
        schedule = self.get_schedule()
        tzinfo = self._tzinfo
        target_dt = ensure_local(datetime.combine(local_date, time(hour=12)), tzinfo)
        return self.period_for_timestamp(target_dt.astimezone(timezone.utc))

    def period_for_timestamp(self, ts_utc: datetime) -> Dict:
        schedule = self.get_schedule()
        row = self.service.get_period_for_timestamp(schedule["id"], ts_utc)
        return self._format_period(schedule, row)

    def get_period(self, period_id: str) -> Dict:
        schedule = self.get_schedule()
        row = self.service.get_period(period_id)
        if row.get("schedule_id") != schedule["id"]:
            # Reformat regardless — even if schedule changed, formatting still works
            schedule = self.service.get_schedule(row["schedule_id"])
        return self._format_period(schedule, row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _format_period(self, schedule: Dict, row: Dict) -> Dict:
        tzinfo = get_timezone(schedule["timezone"])
        start_local = to_local(from_utc_iso(row["start_at_utc"]), tzinfo)
        end_local = to_local(from_utc_iso(row["end_at_utc"]), tzinfo)
        # Pay periods are inclusive from Sunday to Saturday.
        # Stored end_local is the next period's Sunday at 06:00, so display date is end_local - 1 day.
        display_end_date = end_local.date() - timedelta(days=1)
        start_date_iso = start_local.date().isoformat()
        end_date_iso = display_end_date.isoformat()
        start_label = start_local.strftime("%d/%m/%Y")
        end_label = display_end_date.strftime("%d/%m/%Y")
        folder_slug = f"{row['display_id']}_{start_date_iso}_{end_date_iso}"
        return {
            **row,
            "schedule_id": row.get("schedule_id") or schedule["id"],
            "timezone": schedule["timezone"],
            "start_local_iso": start_local.isoformat(timespec="seconds"),
            "end_local_iso": end_local.isoformat(timespec="seconds"),
            "start_date_iso": start_date_iso,
            "end_date_iso": end_date_iso,
            "start_label": start_label,
            "end_label": end_label,
            "range_label": f"{start_label} au {end_label}",
            "folder_slug": folder_slug,
        }
