"""Anchor-based pay period generation and management."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from db.db_manager import db_session
from payroll.time_utils import (
    date_in_local,
    ensure_local,
    get_timezone,
    normalize_date,
    parse_local_iso,
    to_utc_iso,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PayCalendarError(RuntimeError):
    pass


class PayCalendarService:
    """Manage pay schedules and deterministic pay-period generation."""

    def __init__(self, *, default_group: str = "default") -> None:
        self.default_group = default_group

    # ------------------------------------------------------------------
    # Schedule helpers
    # ------------------------------------------------------------------
    def _resolve_group(self, group_key: Optional[str]) -> str:
        return (group_key or self.default_group).strip() or "default"

    def list_schedules(self, *, group_key: Optional[str] = None) -> List[Dict]:
        group = self._resolve_group(group_key)
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pay_schedules
                WHERE group_key = ?
                ORDER BY effective_from DESC
                """,
                (group,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_schedule(self, schedule_id: str) -> Dict:
        if not schedule_id:
            raise PayCalendarError("Identifiant d’horaire invalide")
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM pay_schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
            if not row:
                raise PayCalendarError("Horaire introuvable")
        return dict(row)

    def get_active_schedule(
        self,
        *,
        group_key: Optional[str] = None,
        for_date_local: Optional[date] = None,
    ) -> Dict:
        group = self._resolve_group(group_key)
        target_date = normalize_date(for_date_local or date.today())
        target_iso = target_date.isoformat()
        with db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM pay_schedules
                WHERE group_key = ?
                  AND effective_from <= ?
                  AND (effective_to IS NULL OR effective_to >= ?)
                ORDER BY effective_from DESC
                LIMIT 1
                """,
                (group, target_iso, target_iso),
            ).fetchone()
            if not row:
                raise PayCalendarError(
                    f"Aucun horaire actif pour {group} à la date {target_iso}."
                )
        return dict(row)

    def create_schedule_version(
        self,
        *,
        name: str,
        timezone_name: str,
        period_length_days: int,
        pay_date_offset_days: int,
        anchor_start_local: str,
        effective_from: date,
        group_key: Optional[str] = None,
    ) -> Dict:
        """Insert a new schedule version and close the current one."""
        group = self._resolve_group(group_key)
        if period_length_days < 7 or period_length_days > 31:
            raise PayCalendarError("La durée de période doit être entre 7 et 31 jours.")
        if pay_date_offset_days < 0 or pay_date_offset_days > 30:
            raise PayCalendarError("Le délai de paie doit être entre 0 et 30 jours.")
        tzinfo = get_timezone(timezone_name)
        anchor_dt = parse_local_iso(anchor_start_local, tzinfo)
        if anchor_dt.weekday() != 6 or anchor_dt.hour != 6 or anchor_dt.minute != 0:
            raise PayCalendarError("L’ancre doit être un dimanche à 06:00.")
        eff_from_date = normalize_date(effective_from)
        eff_from_iso = eff_from_date.isoformat()
        close_date = (eff_from_date - timedelta(days=1)).isoformat()
        schedule_id = str(uuid4())
        now = _utc_now()
        with db_session() as conn:
            conn.execute(
                """
                UPDATE pay_schedules
                   SET effective_to = ?, updated_at = ?
                 WHERE group_key = ? AND effective_to IS NULL
                """,
                (close_date, now, group),
            )
            conn.execute(
                """
                INSERT INTO pay_schedules(
                    id, group_key, name, timezone, period_length_days,
                    pay_date_offset_days, anchor_start_local, effective_from,
                    effective_to, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    schedule_id,
                    group,
                    name.strip() or "Pay Schedule",
                    timezone_name,
                    period_length_days,
                    pay_date_offset_days,
                    anchor_start_local,
                    eff_from_iso,
                    now,
                    now,
                ),
            )
        return self.get_schedule(schedule_id)

    # ------------------------------------------------------------------
    # Period generation
    # ------------------------------------------------------------------
    def ensure_periods(
        self,
        schedule_id: str,
        from_local_date: date,
        to_local_date: date,
    ) -> None:
        schedule = self.get_schedule(schedule_id)
        tzinfo = get_timezone(schedule["timezone"])
        anchor_local = parse_local_iso(schedule["anchor_start_local"], tzinfo)
        period_length = timedelta(days=int(schedule["period_length_days"]))
        if period_length <= timedelta(0):
            raise PayCalendarError("Durée de période invalide")
        from_dt = ensure_local(normalize_date(from_local_date), tzinfo)
        to_dt = ensure_local(normalize_date(to_local_date) + timedelta(days=1), tzinfo)

        start_candidate = self._find_start_before(anchor_local, from_dt, period_length)
        starts: List[datetime] = []
        current = start_candidate
        while current < to_dt:
            starts.append(current)
            current = current + period_length

        if not starts:
            return

        pay_offset = int(schedule["pay_date_offset_days"])
        new_rows_by_year: Dict[int, List[Dict]] = defaultdict(list)
        with db_session() as conn:
            for start_local in starts:
                start_utc_iso = to_utc_iso(start_local)
                existing = conn.execute(
                    """
                    SELECT id FROM pay_periods
                    WHERE schedule_id = ? AND start_at_utc = ?
                    """,
                    (schedule_id, start_utc_iso),
                ).fetchone()
                if existing:
                    continue
                end_local = start_local + period_length
                row = {
                    "start_at_utc": start_utc_iso,
                    "end_at_utc": to_utc_iso(end_local),
                    "pay_date_local": (end_local.date() + timedelta(days=pay_offset)).isoformat(),
                    "label_year": start_local.year,
                    "local_start": start_local,
                }
                new_rows_by_year[start_local.year].append(row)

            for year, rows in new_rows_by_year.items():
                if not rows:
                    continue
                self._insert_and_resequence_year(conn, schedule, year, rows)

    def _find_start_before(self, anchor: datetime, target: datetime, period_length: timedelta) -> datetime:
        if target <= anchor:
            current = anchor
            while current - period_length >= target:
                current -= period_length
            return current
        delta = target - anchor
        steps = math.floor(delta / period_length)
        current = anchor + steps * period_length
        while current + period_length <= target:
            current += period_length
        return current

    def _insert_and_resequence_year(
        self,
        conn,
        schedule: Dict,
        label_year: int,
        new_rows: Sequence[Dict],
    ) -> None:
        schedule_id = schedule["id"]
        now = _utc_now()
        period_rows = list(
            conn.execute(
                """
                SELECT id, start_at_utc, sequence_in_year, display_id, status
                FROM pay_periods
                WHERE schedule_id = ? AND label_year = ?
                ORDER BY start_at_utc
                """,
                (schedule_id, label_year),
            ).fetchall()
        )
        combined = [
            {
                "id": row["id"],
                "start_at_utc": row["start_at_utc"],
                "existing": True,
            }
            for row in period_rows
        ]
        for row in new_rows:
            combined.append(
                {
                    "id": None,
                    "start_at_utc": row["start_at_utc"],
                    "data": row,
                    "existing": False,
                }
            )
        combined.sort(key=lambda item: item["start_at_utc"])
        for sequence, item in enumerate(combined, start=1):
            display_id = f"{label_year}-{sequence:02d}"
            if item["existing"]:
                conn.execute(
                    """
                    UPDATE pay_periods
                       SET sequence_in_year = ?, display_id = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (sequence, display_id, now, item["id"]),
                )
            else:
                data = item["data"]
                conn.execute(
                    """
                    INSERT INTO pay_periods(
                        id, schedule_id, start_at_utc, end_at_utc, pay_date_local,
                        label_year, sequence_in_year, display_id, status,
                        locked_at_utc, payed_at_utc, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', NULL, NULL, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        schedule_id,
                        data["start_at_utc"],
                        data["end_at_utc"],
                        data["pay_date_local"],
                        label_year,
                        sequence,
                        display_id,
                        now,
                        now,
                    ),
                )

    # ------------------------------------------------------------------
    # Period queries and state transitions
    # ------------------------------------------------------------------
    def list_periods(
        self,
        schedule_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        with db_session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pay_periods
                WHERE schedule_id = ?
                ORDER BY start_at_utc DESC
                LIMIT ? OFFSET ?
                """,
                (schedule_id, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_period_for_timestamp(
        self,
        schedule_id: str,
        ts_utc: datetime,
    ) -> Dict:
        if ts_utc.tzinfo is None:
            raise PayCalendarError("Datetime doit être aware en UTC.")
        ts_iso = ts_utc.astimezone(timezone.utc).isoformat(timespec="seconds")
        schedule = self.get_schedule(schedule_id)
        with db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM pay_periods
                 WHERE schedule_id = ?
                   AND start_at_utc <= ?
                   AND end_at_utc > ?
                LIMIT 1
                """,
                (schedule_id, ts_iso, ts_iso),
            ).fetchone()
            if row:
                return dict(row)
        tzinfo = get_timezone(schedule["timezone"])
        local_date = date_in_local(ts_utc, tzinfo)
        self.ensure_periods(
            schedule_id,
            local_date - timedelta(days=180),
            local_date + timedelta(days=365),
        )
        with db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM pay_periods
                 WHERE schedule_id = ?
                   AND start_at_utc <= ?
                   AND end_at_utc > ?
                LIMIT 1
                """,
                (schedule_id, ts_iso, ts_iso),
            ).fetchone()
            if not row:
                raise PayCalendarError("Période introuvable après génération.")
        return dict(row)

    def lock_period(self, period_id: str) -> Dict:
        return self._transition_period(period_id, "OPEN", "LOCKED", set_locked=True)

    def mark_payed(self, period_id: str) -> Dict:
        return self._transition_period(period_id, "LOCKED", "PAYED", set_payed=True)

    def _transition_period(
        self,
        period_id: str,
        expected_status: str,
        new_status: str,
        *,
        set_locked: bool = False,
        set_payed: bool = False,
    ) -> Dict:
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM pay_periods WHERE id = ?",
                (period_id,),
            ).fetchone()
            if not row:
                raise PayCalendarError("Période introuvable")
            if row["status"] != expected_status:
                raise PayCalendarError(
                    f"Transition invalide: {row['status']} -> {new_status}"
                )
            now = _utc_now()
            updates = ["status = ?", "updated_at = ?"]
            params: List = [new_status, now]
            if set_locked:
                updates.append("locked_at_utc = ?")
                params.append(now)
            if set_payed:
                updates.append("payed_at_utc = ?")
                params.append(now)
            params.append(period_id)
            conn.execute(
                f"UPDATE pay_periods SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        return self.get_period(period_id)

    def get_period(self, period_id: str) -> Dict:
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM pay_periods WHERE id = ?",
                (period_id,),
            ).fetchone()
            if not row:
                raise PayCalendarError("Période introuvable")
        return dict(row)

    def admin_override_period(
        self,
        period_id: str,
        changes: Dict[str, str],
        *,
        reason: str,
        admin_actor: Optional[str] = None,
    ) -> Dict:
        if not changes:
            return self.get_period(period_id)
        allowed_fields = {"pay_date_local"}
        invalid = set(changes) - allowed_fields
        if invalid:
            raise PayCalendarError(
                f"Champs non autorisés pour override: {', '.join(sorted(invalid))}"
            )
        reason_text = (reason or "").strip()
        if not reason_text:
            raise PayCalendarError("Une raison est requise pour la modification admin.")
        now = _utc_now()
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM pay_periods WHERE id = ?",
                (period_id,),
            ).fetchone()
            if not row:
                raise PayCalendarError("Période introuvable")
            row_dict = dict(row)
            for field, new_value in changes.items():
                old_value = row_dict.get(field)
                if old_value == new_value:
                    continue
                conn.execute(
                    f"UPDATE pay_periods SET {field} = ?, updated_at = ? WHERE id = ?",
                    (new_value, now, period_id),
                )
                conn.execute(
                    """
                    INSERT INTO pay_period_overrides(
                        id, period_id, admin_actor, field_name,
                        old_value, new_value, reason, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        period_id,
                        admin_actor,
                        field,
                        old_value,
                        new_value,
                        reason_text,
                        now,
                    ),
                )
                row_dict[field] = new_value
        return self.get_period(period_id)
