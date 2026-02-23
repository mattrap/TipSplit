"""
Repository layer for employee CRUD operations.

UI modules should only communicate through this module to avoid
sprinkling SQL queries throughout the codebase.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .db_manager import db_session

logger = logging.getLogger("tipsplit.employees")

EMPLOYEE_ROLES = ("service", "busboy")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_role(role: str) -> str:
    if not role:
        raise ValueError("Le rôle est requis (service ou busboy).")
    role = role.strip().lower()
    if role not in EMPLOYEE_ROLES:
        raise ValueError("Rôle invalide. Utilisez 'service' ou 'busboy'.")
    return role


def _normalize_name(name: str) -> str:
    if not name or not str(name).strip():
        raise ValueError("Le nom de l’employé est requis.")
    return str(name).strip()


def _normalize_points(points) -> float:
    try:
        value = float(points)
    except (TypeError, ValueError):
        raise ValueError("Les points doivent être un nombre.")
    return value


def list_employees(
    role: Optional[str] = None,
    active_only: bool = True,
    order_by_points_desc: bool = True,
) -> List[Dict]:
    role_clause = ""
    params: List = []
    if role:
        role_clause = "WHERE role = ?"
        params.append(_normalize_role(role))
    if active_only:
        role_clause += (" AND" if role_clause else "WHERE") + " is_active = 1"

    order = "points DESC, name COLLATE NOCASE ASC" if order_by_points_desc else "name COLLATE NOCASE ASC"
    query = f"""
        SELECT id, name, role, points, employee_number, email, is_active, created_at, updated_at
        FROM employees
        {role_clause}
        ORDER BY {order};
    """
    with db_session() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def add_employee(name: str, role: str, points: float, employee_number: str = "", email: str = "") -> int:
    normalized_name = _normalize_name(name)
    normalized_role = _normalize_role(role)
    normalized_points = _normalize_points(points)
    now = _utc_now()
    try:
        with db_session() as conn:
            cur = conn.execute(
                """
                INSERT INTO employees(name, role, points, employee_number, email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (normalized_name, normalized_role, normalized_points, employee_number.strip(), email.strip(), now, now),
            )
            employee_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Un employé nommé '{normalized_name}' existe déjà pour le rôle {normalized_role}.") from exc

    logger.info("Nouvel employé ajouté (%s #%s)", normalized_role, employee_id)
    return int(employee_id)


def update_employee(
    employee_id: int,
    name: Optional[str] = None,
    role: Optional[str] = None,
    points: Optional[float] = None,
    is_active: Optional[bool] = None,
    employee_number: Optional[str] = None,
    email: Optional[str] = None,
) -> None:
    if not employee_id:
        raise ValueError("Identifiant d’employé manquant.")

    updates = []
    params: List = []
    if name is not None:
        updates.append("name = ?")
        params.append(_normalize_name(name))
    if role is not None:
        updates.append("role = ?")
        params.append(_normalize_role(role))
    if points is not None:
        updates.append("points = ?")
        params.append(_normalize_points(points))
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    if employee_number is not None:
        updates.append("employee_number = ?")
        params.append(employee_number.strip())
    if email is not None:
        updates.append("email = ?")
        params.append(email.strip())

    if not updates:
        return

    updates.append("updated_at = ?")
    params.append(_utc_now())
    params.append(employee_id)

    with db_session() as conn:
        cur = conn.execute(
            f"UPDATE employees SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise ValueError("Employé introuvable pour mise à jour.")


def delete_employee(employee_id: int) -> None:
    """
    Soft delete: employees remain in the DB for historical exports but disappear from active rosters.
    """
    update_employee(employee_id, is_active=False)
    logger.info("Employé %s désactivé", employee_id)


def _fetch_existing_by_role(conn: sqlite3.Connection, role: str) -> Dict[int, Dict]:
    rows = conn.execute(
        "SELECT id, name, employee_number, email, is_active FROM employees WHERE role = ?;",
        (role,),
    ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def upsert_many(role: str, employees_list: Iterable[Dict]) -> Tuple[int, int, int]:
    """
    Bulk replace the roster for a single role with the provided rows.
    employees_list items must contain: id (optional), number, name, points, email
    Returns a tuple of (#inserted, #updated, #deactivated).
    """
    normalized_role = _normalize_role(role)
    now = _utc_now()

    normalized_rows = []
    for raw in employees_list:
        normalized_rows.append(
            {
                "id": raw.get("id"),
                "employee_number": str(raw.get("number", "") or "").strip(),
                "name": _normalize_name(raw.get("name", "")),
                "points": _normalize_points(raw.get("points", 0)),
                "email": str(raw.get("email", "") or "").strip(),
            }
        )

    inserted = updated = 0

    with db_session() as conn:
        existing = _fetch_existing_by_role(conn, normalized_role)
        name_index = {
            (data.get("name") or "").strip().lower(): emp_id
            for emp_id, data in existing.items()
        }
        seen_ids = set()

        for row in normalized_rows:
            emp_id = row["id"]
            name_key = row["name"].lower()

            target_id = emp_id if emp_id and emp_id in existing else None
            if target_id is None:
                match_id = name_index.get(name_key)
                if match_id and match_id not in seen_ids:
                    target_id = match_id

            if target_id:
                try:
                    conn.execute(
                        """
                        UPDATE employees
                        SET name = ?, role = ?, points = ?, employee_number = ?, email = ?, is_active = 1, updated_at = ?
                        WHERE id = ?;
                        """,
                        (
                            row["name"],
                            normalized_role,
                            row["points"],
                            row["employee_number"],
                            row["email"],
                            now,
                            target_id,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError(
                        f"Impossible de renommer '{row['name']}'. Un employé avec ce nom existe déjà."
                    ) from exc
                updated += 1
                seen_ids.add(target_id)
                name_index[name_key] = target_id
            else:
                try:
                    cur = conn.execute(
                        """
                        INSERT INTO employees(name, role, points, employee_number, email, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?);
                        """,
                        (
                            row["name"],
                            normalized_role,
                            row["points"],
                            row["employee_number"],
                            row["email"],
                            now,
                            now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError(
                        f"Impossible d’ajouter '{row['name']}'. Un employé avec ce nom existe déjà."
                    ) from exc
                inserted += 1
                new_id = cur.lastrowid
                seen_ids.add(int(new_id))
                name_index[name_key] = int(new_id)

        existing_active_ids = {eid for eid, data in existing.items() if data["is_active"]}
        to_deactivate = existing_active_ids - seen_ids
        deactivated = 0
        if to_deactivate:
            placeholders = ",".join("?" for _ in to_deactivate)
            conn.execute(
                f"UPDATE employees SET is_active = 0, updated_at = ? WHERE id IN ({placeholders})",
                (now, *to_deactivate),
            )
            deactivated = len(to_deactivate)

    logger.info(
        "Roster enregistré (%s) - ajoutés: %s, mis à jour: %s, désactivés: %s",
        normalized_role,
        inserted,
        updated,
        deactivated,
    )
    return inserted, updated, deactivated
