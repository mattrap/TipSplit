"""Authentication and Supabase sync helpers for TipSplit."""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, Optional

import bcrypt
import requests

from AppConfig import (
    get_auth_cache_path,
    get_last_auth_sync,
    get_supabase_settings,
    set_last_auth_sync,
)


class SupabaseConfigurationError(Exception):
    """Raised when Supabase URL or service key is missing."""


class SupabaseSyncError(Exception):
    """Raised when the remote Supabase call fails."""


class AuthenticationError(Exception):
    """Base authentication exception."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when the email/password combination is incorrect."""


class AccountStatusError(AuthenticationError):
    """Raised when the account exists but is disabled remotely."""


@dataclass
class AuthResult:
    email: str
    status: str
    updated_at: str


class AuthManager:
    """Handles Supabase synchronisation and offline authentication."""

    def __init__(self, cache_path: Optional[str] = None):
        self.cache_path = cache_path or get_auth_cache_path()
        self.cache: Dict[str, Dict[str, Dict[str, str]]] = self._load_cache()
        self.offline_mode = False
        self.last_sync = self.cache.get("last_sync") or get_last_auth_sync()

    # ----------------------------
    # Cache helpers
    # ----------------------------
    @staticmethod
    def _normalize_email(value: str) -> str:
        return (value or "").strip().lower()

    def _load_cache(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        if not self.cache_path or not os.path.exists(self.cache_path):
            return {"users": {}, "last_sync": ""}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):  # pragma: no cover - defensive
                raise ValueError("Cache should be a JSON object")
            data.setdefault("users", {})
            data.setdefault("last_sync", "")
            return data
        except Exception:
            return {"users": {}, "last_sync": ""}

    def _atomic_write_cache(self, data: Dict[str, object]):
        directory = os.path.dirname(self.cache_path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="auth_cache_", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp_path, self.cache_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise

    # ----------------------------
    # Public API
    # ----------------------------
    def has_cached_users(self) -> bool:
        return bool(self.cache.get("users"))

    def sync(self, *, timeout: int = 10) -> int:
        settings = get_supabase_settings()
        url = (settings.get("url") or "").strip()
        service_key = (settings.get("service_key") or "").strip()
        if not url or not service_key:
            self.offline_mode = True
            raise SupabaseConfigurationError("Supabase URL ou service key manquante.")

        endpoint = url.rstrip("/") + "/rest/v1/users?select=email,password_hash,status,updated_at"
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(endpoint, headers=headers, timeout=timeout)
        except requests.RequestException as exc:  # pragma: no cover - network errors
            self.offline_mode = True
            raise SupabaseSyncError(str(exc)) from exc

        if response.status_code >= 400:
            self.offline_mode = True
            raise SupabaseSyncError(f"HTTP {response.status_code}: {response.text[:120]}")

        try:
            payload = response.json()
        except ValueError as exc:
            self.offline_mode = True
            raise SupabaseSyncError("Réponse Supabase invalide.") from exc

        users: Dict[str, Dict[str, str]] = {}
        for row in payload:
            email = self._normalize_email(row.get("email", ""))
            if not email:
                continue
            password_hash = (row.get("password_hash") or "").strip()
            status = (row.get("status") or "").strip().lower() or "disabled"
            updated_at = (row.get("updated_at") or "").strip()
            users[email] = {
                "email": row.get("email", email),
                "password_hash": password_hash,
                "status": status,
                "updated_at": updated_at,
            }

        timestamp = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        cache_payload = {"users": users, "last_sync": timestamp}
        self._atomic_write_cache(cache_payload)
        set_last_auth_sync(timestamp)
        self.cache = cache_payload
        self.last_sync = timestamp
        self.offline_mode = False
        return len(users)

    def authenticate(self, email: str, password: str) -> AuthResult:
        if not email or not password:
            raise InvalidCredentialsError("Courriel et mot de passe requis.")

        normalized = self._normalize_email(email)
        record = self.cache.get("users", {}).get(normalized)
        if not record:
            raise InvalidCredentialsError("Identifiants inconnus.")

        stored_hash = record.get("password_hash", "")
        if not stored_hash:
            raise InvalidCredentialsError("Mot de passe invalide.")

        try:
            matches = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError as exc:  # pragma: no cover - malformed hashes
            raise InvalidCredentialsError("Mot de passe invalide.") from exc

        if not matches:
            raise InvalidCredentialsError("Mot de passe incorrect.")

        status = (record.get("status") or "").lower()
        if status not in {"", "active"}:
            raise AccountStatusError(status)

        return AuthResult(
            email=record.get("email") or normalized,
            status=status or "active",
            updated_at=record.get("updated_at", ""),
        )

    def reload_cache(self):
        self.cache = self._load_cache()

    def get_cached_user_count(self) -> int:
        return len(self.cache.get("users", {}))

