"""
Database initialization and connection helpers for TipSplit.

This module centralizes the SQLite path resolution (user data dir aware),
schema creation, and lightweight migration/version tracking.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from typing import Iterator, Optional

from datetime import datetime, timezone

try:
    from platformdirs import user_data_dir  # type: ignore
except Exception:  # pragma: no cover - platformdirs is optional
    user_data_dir = None

from AppConfig import get_user_data_dir

APP_NAME = "TipSplit"
DB_FILENAME = "tipsplit.db"
SCHEMA_VERSION = 3

logger = logging.getLogger("tipsplit.db")


def get_app_data_dir() -> str:
    """
    Return the per-user application data directory.
    Prefers AppConfig (portable aware), then platformdirs, finally manual fallbacks.
    """
    try:
        base = get_user_data_dir()
    except Exception:
        base = None

    if not base:
        if user_data_dir:
            try:
                base = user_data_dir(APP_NAME, APP_NAME)
            except Exception:
                base = None
        if not base:
            # Manual fallback for the three major OS families
            home = os.path.expanduser("~")
            if os.name == "nt":
                base = os.path.join(os.environ.get("APPDATA", home), APP_NAME)
            elif sys.platform == "darwin":
                base = os.path.join(home, "Library", "Application Support", APP_NAME)
            else:
                base = os.path.join(home, ".local", "share", APP_NAME)

    os.makedirs(base, exist_ok=True)
    return base


def get_db_path() -> str:
    """Absolute path to tipsplit.db (auto-creates parent directories)."""
    env_override = os.environ.get("TIPSPLIT_DB_PATH", "").strip()
    if env_override:
        path = os.path.expanduser(env_override)
    else:
        data_dir = get_app_data_dir()
        path = os.path.join(data_dir, DB_FILENAME)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    """
    Create a connection to the TipSplit database.
    The caller is responsible for closing it.
    """
    path = get_db_path()
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    """
    Convenience context manager for one-off operations that need
    transaction handling and consistent logging.
    """
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """
    Ensure the database file exists, schema is applied, and schema version recorded.
    Safe to call multiple times.
    """
    path = get_db_path()
    logger.info("Initializing TipSplit database at %s", path)
    with db_session() as conn:
        apply_migrations(conn)


def apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Initialize or migrate the schema to the latest version.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    current_version = int(row["value"]) if row else None

    if current_version is None:
        logger.info("Initializing schema version %s", SCHEMA_VERSION)
        _create_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        return

    if current_version == SCHEMA_VERSION:
        logger.info("Schema version %s already applied", current_version)
        return

    if current_version == 2 and SCHEMA_VERSION == 3:
        logger.info("Migrating schema 2 -> 3")
        _migrate_2_to_3(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        return

    logger.warning("Unsupported schema version %s; reinitializing schema %s", current_version, SCHEMA_VERSION)
    _create_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )


def _create_schema(conn: sqlite3.Connection) -> None:
    """
    Create the full schema from scratch. Safe because no production data exists yet.
    """
    # Drop old development tables to avoid conflicts when iterating locally.
    conn.execute("DROP TABLE IF EXISTS distribution_audit;")
    conn.execute("DROP TABLE IF EXISTS distribution_employees;")
    conn.execute("DROP TABLE IF EXISTS distribution_declaration_inputs;")
    conn.execute("DROP TABLE IF EXISTS distribution_inputs;")
    conn.execute("DROP TABLE IF EXISTS distributions;")
    conn.execute("DROP TABLE IF EXISTS pay_period_overrides;")
    conn.execute("DROP TABLE IF EXISTS pay_periods;")
    conn.execute("DROP TABLE IF EXISTS pay_schedules;")
    conn.execute("DROP TABLE IF EXISTS shifts;")
    conn.execute("DROP TABLE IF EXISTS employees;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('service','busboy')),
            points REAL NOT NULL DEFAULT 0,
            employee_number TEXT,
            email TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(role, name COLLATE NOCASE)
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_employees_role_active
        ON employees(role, is_active);
        """
    )
    conn.execute(
        """
        CREATE TABLE pay_schedules (
            id TEXT PRIMARY KEY,
            group_key TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'America/Montreal',
            period_length_days INTEGER NOT NULL DEFAULT 14,
            pay_date_offset_days INTEGER NOT NULL DEFAULT 4,
            anchor_start_local TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pay_schedules_group
        ON pay_schedules(group_key, effective_from);
        """
    )

    conn.execute(
        """
        CREATE TABLE pay_periods (
            id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL,
            start_at_utc TEXT NOT NULL,
            end_at_utc TEXT NOT NULL,
            pay_date_local TEXT NOT NULL,
            label_year INTEGER NOT NULL,
            sequence_in_year INTEGER NOT NULL,
            display_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN','LOCKED','PAYED')) DEFAULT 'OPEN',
            locked_at_utc TEXT,
            payed_at_utc TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(schedule_id) REFERENCES pay_schedules(id) ON DELETE CASCADE,
            UNIQUE(schedule_id, start_at_utc),
            UNIQUE(schedule_id, display_id),
            CHECK(end_at_utc > start_at_utc)
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pay_periods_sched_start
        ON pay_periods(schedule_id, start_at_utc);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pay_periods_sched_end
        ON pay_periods(schedule_id, end_at_utc);
        """
    )

    conn.execute(
        """
        CREATE TABLE pay_period_overrides (
            id TEXT PRIMARY KEY,
            period_id TEXT NOT NULL,
            admin_actor TEXT,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(period_id) REFERENCES pay_periods(id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE shifts (
            id TEXT PRIMARY KEY,
            employee_id INTEGER,
            period_id TEXT NOT NULL,
            shift_start_at_utc TEXT NOT NULL,
            shift_end_at_utc TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(employee_id) REFERENCES employees(id),
            FOREIGN KEY(period_id) REFERENCES pay_periods(id)
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shifts_period
        ON shifts(period_id);
        """
    )

    conn.execute(
        """
        CREATE TABLE distributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dist_ref TEXT UNIQUE,
            pay_period_id TEXT NOT NULL,
            date_local TEXT NOT NULL,
            shift TEXT NOT NULL,
            shift_instance INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL CHECK(status IN ('UNCONFIRMED','CONFIRMED')) DEFAULT 'UNCONFIRMED',
            created_at TEXT NOT NULL,
            confirmed_at TEXT,
            created_by TEXT,
            confirmed_by TEXT,
            FOREIGN KEY(pay_period_id) REFERENCES pay_periods(id) ON DELETE CASCADE,
            UNIQUE(pay_period_id, date_local, shift, shift_instance)
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_period_status
        ON distributions(pay_period_id, status);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_date
        ON distributions(date_local);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_day_shift
        ON distributions(pay_period_id, date_local, shift, shift_instance);
        """
    )


def _migrate_2_to_3(conn: sqlite3.Connection) -> None:
    """Add shift_instance to distributions and update uniqueness constraint."""
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS distributions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dist_ref TEXT UNIQUE,
            pay_period_id TEXT NOT NULL,
            date_local TEXT NOT NULL,
            shift TEXT NOT NULL,
            shift_instance INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL CHECK(status IN ('UNCONFIRMED','CONFIRMED')) DEFAULT 'UNCONFIRMED',
            created_at TEXT NOT NULL,
            confirmed_at TEXT,
            created_by TEXT,
            confirmed_by TEXT,
            FOREIGN KEY(pay_period_id) REFERENCES pay_periods(id) ON DELETE CASCADE,
            UNIQUE(pay_period_id, date_local, shift, shift_instance)
        );
        """
    )
    conn.execute(
        """
        INSERT INTO distributions_new(
            id, dist_ref, pay_period_id, date_local, shift, shift_instance,
            status, created_at, confirmed_at, created_by, confirmed_by
        )
        SELECT
            id, dist_ref, pay_period_id, date_local, shift, 1,
            status, created_at, confirmed_at, created_by, confirmed_by
        FROM distributions;
        """
    )
    conn.execute("DROP TABLE distributions;")
    conn.execute("ALTER TABLE distributions_new RENAME TO distributions;")
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_period_status
        ON distributions(pay_period_id, status);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_date
        ON distributions(date_local);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distributions_day_shift
        ON distributions(pay_period_id, date_local, shift, shift_instance);
        """
    )
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_inputs (
            distribution_id INTEGER PRIMARY KEY,
            ventes_nettes REAL,
            depot_net REAL,
            frais_admin REAL,
            cash REAL,
            FOREIGN KEY(distribution_id) REFERENCES distributions(id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_declaration_inputs (
            distribution_id INTEGER PRIMARY KEY,
            ventes_totales REAL,
            clients INTEGER,
            tips_due REAL,
            ventes_nourriture REAL,
            FOREIGN KEY(distribution_id) REFERENCES distributions(id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distribution_id INTEGER NOT NULL,
            employee_number TEXT,
            employee_name TEXT NOT NULL,
            section TEXT,
            hours REAL,
            cash REAL,
            sur_paye REAL,
            frais_admin REAL,
            A REAL,
            B REAL,
            D REAL,
            E REAL,
            F REAL,
            FOREIGN KEY(distribution_id) REFERENCES distributions(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_distribution_employees_dist
        ON distribution_employees(distribution_id);
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distribution_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            actor TEXT,
            created_at TEXT NOT NULL,
            details_json TEXT,
            FOREIGN KEY(distribution_id) REFERENCES distributions(id) ON DELETE CASCADE
        );
        """
    )
