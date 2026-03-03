import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from db.db_manager import init_db, db_session


class DbManagerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "legacy.db")
        os.environ["TIPSPLIT_DB_PATH"] = self.db_path

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("TIPSPLIT_DB_PATH", None)

    def test_init_db_preserves_existing_data_without_metadata(self):
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE employees (
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
                "INSERT INTO employees(name, role, points, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("Alice", "service", 2.5, created_at, created_at),
            )
            conn.commit()

        init_db()

        with db_session() as conn:
            row = conn.execute("SELECT name, points FROM employees").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Alice")
            self.assertEqual(row["points"], 2.5)
            meta = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            self.assertIsNotNone(meta)


if __name__ == "__main__":
    unittest.main()
