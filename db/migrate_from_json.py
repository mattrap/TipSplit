"""
One-time migration helper that imports legacy employee JSON files into SQLite.

Safe to run multiple times: it only executes when the employees table is empty.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from AppConfig import get_backend_dir
from .db_manager import db_session

logger = logging.getLogger("tipsplit.migration")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

LEGACY_FILES = {
    "service": "service_employees.json",
    "busboy": "bussboy_employees.json",
}


def _legacy_paths() -> Dict[str, str]:
    override = os.environ.get("TIPSPLIT_BACKEND_DIR", "").strip()
    if override:
        backend = os.path.expanduser(override)
    else:
        backend = get_backend_dir()
    os.makedirs(backend, exist_ok=True)
    return {role: os.path.join(backend, filename) for role, filename in LEGACY_FILES.items()}


def _load_legacy_file(path: str) -> List[List]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
    except Exception as exc:
        logger.warning("Impossible de lire %s: %s", path, exc)
    return []


def _table_is_empty() -> bool:
    with db_session() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM employees;").fetchone()
    return bool(row) and row["total"] == 0


def migrate_if_needed() -> None:
    """Populate the employees table from legacy JSON files (once)."""
    try:
        empty = _table_is_empty()
    except Exception as exc:
        logger.error("Impossible de vérifier l’état de la table employees: %s", exc, exc_info=True)
        return

    if not empty:
        logger.info("Migration ignorée (des employés existent déjà).")
        return

    paths = _legacy_paths()
    available = {role: path for role, path in paths.items() if os.path.exists(path)}
    if not available:
        logger.info("Aucun fichier d’employés legacy trouvé pour migration.")
        return

    payloads: List[Tuple[str, Dict[str, str]]] = []
    for role, path in available.items():
        rows = _load_legacy_file(path)
        for idx, row in enumerate(rows):
            try:
                number = str(row[0]) if len(row) > 0 and row[0] is not None else ""
                name = str(row[1]) if len(row) > 1 and row[1] else ""
                points = float(row[2]) if len(row) > 2 else 0.0
                email = str(row[3]) if len(row) > 3 else ""
            except Exception:
                logger.warning("Entrée invalide dans %s (index %s), ignorée.", path, idx)
                continue
            if not name:
                logger.warning("Entrée sans nom dans %s (index %s), ignorée.", path, idx)
                continue
            payloads.append(
                (
                    role,
                    {
                        "name": name,
                        "points": points,
                        "employee_number": number,
                        "email": email,
                    },
                )
            )

    if not payloads:
        logger.info("Fichiers legacy présents mais aucune entrée valide trouvée.")
        return

    per_role = {"service": 0, "busboy": 0}
    with db_session() as conn:
        for role, row in payloads:
            conn.execute(
                """
                INSERT INTO employees(name, role, points, employee_number, email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (row["name"], role, row["points"], row["employee_number"], row["email"], _utc_now(), _utc_now()),
            )
            per_role[role] = per_role.get(role, 0) + 1

    inserted = sum(per_role.values())
    logger.info(
        "Migration JSON terminée: %s employés (service=%s, bussboy=%s).",
        inserted,
        per_role.get("service", 0),
        per_role.get("busboy", 0),
    )

    for _, path in available.items():
        backup_path = f"{path}.bak"
        try:
            os.replace(path, backup_path)
            logger.info("Fichier legacy renommé: %s -> %s", path, backup_path)
        except Exception as exc:
            logger.warning("Impossible de renommer %s vers %s: %s", path, backup_path, exc)
