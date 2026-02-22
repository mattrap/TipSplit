"""
Repository layer for distribution storage (SQLite).

This replaces JSON exports as the source of truth.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .db_manager import db_session

logger = logging.getLogger("tipsplit.distributions")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num_or_none(value) -> Optional[float]:
    if value in ("", None):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except Exception:
        return None


def _int_or_none(value) -> Optional[int]:
    if value in ("", None):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return int(float(value))
    except Exception:
        return None


def _to_date_iso(date_str: str) -> str:
    if not date_str:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    if re.match(r"^\d{2}-\d{2}-\d{4}$", date_str):
        try:
            dt = datetime.strptime(date_str, "%d-%m-%Y")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return ""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def create_distribution(
    *,
    pay_period_id: str,
    date_local: str,
    shift: str,
    shift_instance: int = 1,
    inputs: Dict,
    declaration_inputs: Dict,
    employees: Iterable[Dict],
    created_by: str = "",
) -> Dict:
    if not pay_period_id:
        raise ValueError("pay_period_id manquant.")
    if not date_local:
        raise ValueError("date_local manquante.")
    if not shift:
        raise ValueError("shift manquant.")
    if not isinstance(shift_instance, int) or shift_instance < 1:
        raise ValueError("shift_instance invalide.")

    now = _utc_now()
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO distributions(
                pay_period_id, date_local, shift, shift_instance, status,
                created_at, created_by
            )
            VALUES (?, ?, ?, ?, 'UNCONFIRMED', ?, ?)
            """,
            (pay_period_id, date_local, shift.upper(), shift_instance, now, created_by or ""),
        )
        dist_id = int(cur.lastrowid)

        date_iso = _to_date_iso(date_local)
        year = date_iso[:4] if date_iso else "0000"
        dist_ref = f"DIST-{year}-{dist_id:06d}"
        conn.execute(
            "UPDATE distributions SET dist_ref = ? WHERE id = ?",
            (dist_ref, dist_id),
        )

        conn.execute(
            """
            INSERT INTO distribution_inputs(
                distribution_id, ventes_nettes, depot_net, frais_admin, cash
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dist_id,
                _num_or_none(inputs.get("Ventes Nettes")),
                _num_or_none(inputs.get("Dépot Net")),
                _num_or_none(inputs.get("Frais Admin")),
                _num_or_none(inputs.get("Cash")),
            ),
        )

        conn.execute(
            """
            INSERT INTO distribution_declaration_inputs(
                distribution_id, ventes_totales, clients, tips_due, ventes_nourriture
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dist_id,
                _num_or_none(declaration_inputs.get("Ventes Totales")),
                _int_or_none(declaration_inputs.get("Clients")),
                _num_or_none(declaration_inputs.get("Tips due")),
                _num_or_none(declaration_inputs.get("Ventes Nourriture")),
            ),
        )

        for emp in employees:
            if not isinstance(emp, dict):
                continue
            conn.execute(
                """
                INSERT INTO distribution_employees(
                    distribution_id, employee_number, employee_name, section,
                    hours, cash, sur_paye, frais_admin,
                    A, B, D, E, F
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dist_id,
                    str(emp.get("employee_id") or "") if emp.get("employee_id") not in (None, "") else "",
                    str(emp.get("name") or "").strip(),
                    str(emp.get("section") or "").strip(),
                    _num_or_none(emp.get("hours")),
                    _num_or_none(emp.get("cash")),
                    _num_or_none(emp.get("sur_paye")),
                    _num_or_none(emp.get("frais_admin")),
                    _num_or_none(emp.get("A")),
                    _num_or_none(emp.get("B")),
                    _num_or_none(emp.get("D")),
                    _num_or_none(emp.get("E")),
                    _num_or_none(emp.get("F")),
                ),
            )

        _log_action(
            conn,
            dist_id,
            action="created",
            actor=created_by,
            details={"date_local": date_local, "shift": shift.upper(), "shift_instance": shift_instance},
        )

    logger.info("Distribution créée %s (%s %s)", dist_ref, date_local, shift)
    return {"id": dist_id, "dist_ref": dist_ref, "created_at": now}


def list_period_ids_with_distributions(status: Optional[str] = None) -> List[str]:
    params: List = []
    clause = ""
    if status:
        clause = "WHERE status = ?"
        params.append(status.upper())
    with db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT pay_period_id
            FROM distributions
            {clause}
            ORDER BY pay_period_id
            """,
            params,
        ).fetchall()
    return [row["pay_period_id"] for row in rows]


def list_period_ids_with_distributions_for_periods(period_ids: Iterable[str]) -> List[str]:
    ids = [pid for pid in period_ids if pid]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT pay_period_id
            FROM distributions
            WHERE pay_period_id IN ({placeholders})
            """,
            ids,
        ).fetchall()
    return [row["pay_period_id"] for row in rows]


def list_distributions(
    *,
    pay_period_id: str,
    status: Optional[str] = None,
) -> List[Dict]:
    if not pay_period_id:
        return []
    params: List = [pay_period_id]
    clause = ""
    if status:
        clause = "AND status = ?"
        params.append(status.upper())
    with db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT id, dist_ref, date_local, shift, shift_instance, status, created_at, confirmed_at
            FROM distributions
            WHERE pay_period_id = ?
            {clause}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_distribution(dist_id: int) -> Optional[Dict]:
    if not dist_id:
        return None
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT id, dist_ref, pay_period_id, date_local, shift, shift_instance,
                   status, created_at, confirmed_at, created_by, confirmed_by
            FROM distributions
            WHERE id = ?
            """,
            (dist_id,),
        ).fetchone()
        if not row:
            return None
        inputs_row = conn.execute(
            """
            SELECT ventes_nettes, depot_net, frais_admin, cash
            FROM distribution_inputs
            WHERE distribution_id = ?
            """,
            (dist_id,),
        ).fetchone()
        decl_row = conn.execute(
            """
            SELECT ventes_totales, clients, tips_due, ventes_nourriture
            FROM distribution_declaration_inputs
            WHERE distribution_id = ?
            """,
            (dist_id,),
        ).fetchone()
        employees = conn.execute(
            """
            SELECT employee_number, employee_name, section,
                   hours, cash, sur_paye, frais_admin, A, B, D, E, F
            FROM distribution_employees
            WHERE distribution_id = ?
            ORDER BY id ASC
            """,
            (dist_id,),
        ).fetchall()

    inputs = {}
    if inputs_row:
        inputs = {
            "Ventes Nettes": inputs_row["ventes_nettes"],
            "Dépot Net": inputs_row["depot_net"],
            "Frais Admin": inputs_row["frais_admin"],
            "Cash": inputs_row["cash"],
        }
    decl_inputs = {}
    if decl_row:
        decl_inputs = {
            "Ventes Totales": decl_row["ventes_totales"],
            "Clients": decl_row["clients"],
            "Tips due": decl_row["tips_due"],
            "Ventes Nourriture": decl_row["ventes_nourriture"],
        }

    base = dict(row)
    base["date_iso"] = _to_date_iso(base.get("date_local") or "")
    return {
        **base,
        "inputs": inputs,
        "declaration_inputs": decl_inputs,
        "employees": [dict(emp) for emp in employees],
    }


def find_distribution_by_key(
    *,
    pay_period_id: str,
    date_local: str,
    shift: str,
    shift_instance: int,
) -> Optional[Dict]:
    if not pay_period_id or not date_local or not shift:
        return None
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT id, dist_ref, date_local, shift, shift_instance, status, created_at, confirmed_at
            FROM distributions
            WHERE pay_period_id = ? AND date_local = ? AND shift = ? AND shift_instance = ?
            """,
            (pay_period_id, date_local, shift.upper(), shift_instance),
        ).fetchone()
    return dict(row) if row else None


def list_distributions_by_date_shift(
    *,
    pay_period_id: str,
    date_local: str,
    shift: str,
) -> List[Dict]:
    if not pay_period_id or not date_local or not shift:
        return []
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, dist_ref, date_local, shift, shift_instance, status, created_at, confirmed_at
            FROM distributions
            WHERE pay_period_id = ? AND date_local = ? AND shift = ?
            ORDER BY shift_instance ASC, created_at ASC, id ASC
            """,
            (pay_period_id, date_local, shift.upper()),
        ).fetchall()
    return [dict(row) for row in rows]


def next_shift_instance(
    *,
    pay_period_id: str,
    date_local: str,
    shift: str,
) -> int:
    if not pay_period_id or not date_local or not shift:
        return 1
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT MAX(shift_instance) AS max_inst
            FROM distributions
            WHERE pay_period_id = ? AND date_local = ? AND shift = ?
            """,
            (pay_period_id, date_local, shift.upper()),
        ).fetchone()
    max_inst = row["max_inst"] if row and row["max_inst"] is not None else 0
    return int(max_inst) + 1


def get_distributions_for_period(
    *,
    pay_period_id: str,
    status: Optional[str] = None,
) -> List[Dict]:
    dists = list_distributions(pay_period_id=pay_period_id, status=status)
    results = []
    for dist in dists:
        full = get_distribution(dist["id"])
        if not full:
            continue
        results.append(full)
    return results


def set_distribution_status(dist_id: int, status: str, actor: str = "") -> None:
    if not dist_id:
        raise ValueError("Identifiant de distribution manquant.")
    status = (status or "").upper()
    if status not in ("UNCONFIRMED", "CONFIRMED"):
        raise ValueError("Statut invalide.")
    now = _utc_now()
    with db_session() as conn:
        if status == "CONFIRMED":
            conn.execute(
                """
                UPDATE distributions
                   SET status = ?, confirmed_at = ?, confirmed_by = ?
                 WHERE id = ?
                """,
                (status, now, actor or "", dist_id),
            )
        else:
            conn.execute(
                """
                UPDATE distributions
                   SET status = ?, confirmed_at = NULL, confirmed_by = NULL
                 WHERE id = ?
                """,
                (status, dist_id),
            )
        _log_action(conn, dist_id, action=f"status:{status}", actor=actor)


def delete_distribution(dist_id: int, actor: str = "") -> None:
    if not dist_id:
        raise ValueError("Identifiant de distribution manquant.")
    with db_session() as conn:
        _log_action(conn, dist_id, action="deleted", actor=actor)
        conn.execute("DELETE FROM distributions WHERE id = ?", (dist_id,))


def _log_action(conn, dist_id: int, *, action: str, actor: str = "", details: Optional[Dict] = None) -> None:
    try:
        conn.execute(
            """
            INSERT INTO distribution_audit(distribution_id, action, actor, created_at, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dist_id,
                action,
                actor or "",
                _utc_now(),
                json.dumps(details or {}, ensure_ascii=False),
            ),
        )
    except Exception:
        # Never block the app if logging fails
        pass
