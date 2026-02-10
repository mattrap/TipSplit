"""
Manual smoke-test for the TipSplit database stack.

Run with:  python -m db.self_test
This uses a temporary database file (does not touch production data).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile

# Use a temporary DB so the self-test never mutates the user's roster.
_TEMP_DIR = tempfile.mkdtemp(prefix="tipsplit-selftest-")
os.environ["TIPSPLIT_DB_PATH"] = os.path.join(_TEMP_DIR, "tipsplit-selftest.db")

from .db_manager import get_db_path, init_db
from . import employees_repo


def run_self_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logging.info("Fichier DB temporaire: %s", get_db_path())

    init_db()

    # CRUD cycle
    emp_id = employees_repo.add_employee("Test Service", "service", 7, employee_number="01", email="service@test")
    employees_repo.update_employee(emp_id, points=8)
    employees_repo.add_employee("Test Bussboy", "busboy", 3, employee_number="B01")

    current = employees_repo.list_employees(role="service")
    assert any(e["id"] == emp_id for e in current)

    employees_repo.upsert_many(
        "service",
        [
            {"id": emp_id, "number": "01", "name": "Test Service", "points": 9, "email": "service@test"},
            {"id": None, "number": "02", "name": "Temp Employé", "points": 5, "email": ""},
        ],
    )

    employees_repo.delete_employee(emp_id)

    logging.info("Self-test terminé avec succès.")


def _cleanup():
    try:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    except Exception:
        pass
    for var in ("TIPSPLIT_DB_PATH",):
        os.environ.pop(var, None)


if __name__ == "__main__":
    try:
        run_self_test()
    finally:
        _cleanup()
