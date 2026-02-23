import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

from db.db_manager import init_db, db_session
from payroll.pay_calendar import PayCalendarError, PayCalendarService
from payroll.time_utils import get_timezone, to_utc_iso


class PayCalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["TIPSPLIT_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        init_db()
        self.service = PayCalendarService()

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("TIPSPLIT_DB_PATH", None)

    def _create_schedule(self, anchor_str: str, effective: date):
        return self.service.create_schedule_version(
            name="Test",
            timezone_name="America/Montreal",
            period_length_days=14,
            pay_date_offset_days=4,
            anchor_start_local=anchor_str,
            effective_from=effective,
        )

    def test_boundary_inclusion(self):
        schedule = self._create_schedule("2025-01-05T06:00:00", date(2025, 1, 5))
        self.service.ensure_periods(schedule["id"], date(2024, 12, 20), date(2025, 2, 1))
        tz = get_timezone("America/Montreal")
        start_local = datetime(2025, 1, 5, 6, 0, tzinfo=tz)
        prev_local = start_local - timedelta(seconds=1)
        period = self.service.get_period_for_timestamp(schedule["id"], start_local.astimezone(timezone.utc))
        previous = self.service.get_period_for_timestamp(schedule["id"], prev_local.astimezone(timezone.utc))
        self.assertEqual(period["start_at_utc"], to_utc_iso(start_local))
        self.assertNotEqual(period["id"], previous["id"])

    def test_year_labeling_uses_start_year(self):
        schedule = self._create_schedule("2024-12-29T06:00:00", date(2024, 12, 29))
        self.service.ensure_periods(schedule["id"], date(2024, 12, 1), date(2025, 2, 1))
        tz = get_timezone("America/Montreal")
        dec_period = self.service.get_period_for_timestamp(
            schedule["id"], datetime(2024, 12, 29, 10, 0, tzinfo=tz).astimezone(timezone.utc)
        )
        jan_period = self.service.get_period_for_timestamp(
            schedule["id"], datetime(2025, 1, 12, 10, 0, tzinfo=tz).astimezone(timezone.utc)
        )
        self.assertTrue(dec_period["display_id"].startswith("2024-"))
        self.assertTrue(jan_period["display_id"].startswith("2025-"))

    def test_generation_idempotent(self):
        schedule = self._create_schedule("2025-01-05T06:00:00", date(2025, 1, 5))
        window_start = date(2025, 1, 1)
        window_end = date(2025, 4, 1)
        self.service.ensure_periods(schedule["id"], window_start, window_end)
        with db_session() as conn:
            count_before = conn.execute("SELECT COUNT(*) AS c FROM pay_periods").fetchone()["c"]
        self.service.ensure_periods(schedule["id"], window_start, window_end)
        with db_session() as conn:
            count_after = conn.execute("SELECT COUNT(*) AS c FROM pay_periods").fetchone()["c"]
        self.assertEqual(count_before, count_after)

    def test_status_transitions(self):
        schedule = self._create_schedule("2025-01-05T06:00:00", date(2025, 1, 5))
        self.service.ensure_periods(schedule["id"], date(2025, 1, 1), date(2025, 1, 30))
        with db_session() as conn:
            period_id = conn.execute(
                "SELECT id FROM pay_periods WHERE schedule_id = ? ORDER BY start_at_utc LIMIT 1",
                (schedule["id"],),
            ).fetchone()["id"]
        locked = self.service.lock_period(period_id)
        self.assertEqual(locked["status"], "LOCKED")
        with self.assertRaises(PayCalendarError):
            self.service.lock_period(period_id)
        payed = self.service.mark_payed(period_id)
        self.assertEqual(payed["status"], "PAYED")

    def test_admin_override_tracks_audit(self):
        schedule = self._create_schedule("2025-01-05T06:00:00", date(2025, 1, 5))
        self.service.ensure_periods(schedule["id"], date(2025, 1, 1), date(2025, 1, 30))
        with db_session() as conn:
            row = conn.execute(
                "SELECT id, pay_date_local FROM pay_periods WHERE schedule_id = ? ORDER BY start_at_utc LIMIT 1",
                (schedule["id"],),
            ).fetchone()
            period_id = row["id"]
        new_date = "2025-01-25"
        updated = self.service.admin_override_period(
            period_id,
            {"pay_date_local": new_date},
            reason="Test override",
            admin_actor="unit-test",
        )
        self.assertEqual(updated["pay_date_local"], new_date)
        with db_session() as conn:
            audit = conn.execute(
                "SELECT COUNT(*) AS c FROM pay_period_overrides WHERE period_id = ?",
                (period_id,),
            ).fetchone()["c"]
        self.assertEqual(audit, 1)


if __name__ == "__main__":
    unittest.main()
