"""Authentication and profile access service for the TipSplit desktop app."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import httpx


class AuthErrorCode(str, Enum):
    """Enumeration of authentication error categories."""

    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_DISABLED = "account_disabled"
    PROFILE_MISSING = "profile_missing"
    NETWORK = "network"
    UNKNOWN = "unknown"


class AuthError(RuntimeError):
    """Raised when authentication or authorization fails."""

    def __init__(self, message: str, code: AuthErrorCode = AuthErrorCode.UNKNOWN):
        super().__init__(message)
        self.code = code


@dataclass
class AuthSession:
    """Holds the authentication session tokens."""

    access_token: str
    refresh_token: str
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        # Refresh 30 seconds before the actual expiry to avoid races.
        return now >= self.expires_at - timedelta(seconds=30)


class AuthService:
    """Service responsible for interacting with Supabase Auth and REST APIs."""

    def __init__(self, supabase_url: str, anon_key: str, timeout: float = 10.0) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        self._anon_key = anon_key
        self._timeout = timeout
        self._http_client = httpx.Client(base_url=self._supabase_url, timeout=self._timeout)
        self._session_lock = threading.Lock()
        self._session: Optional[AuthSession] = None
        self._user: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def sign_in(self, email: str, password: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Authenticate the user with Supabase email/password."""

        payload = {"email": email, "password": password}
        print("[AuthService] Login attempt for", email)
        try:
            response = self._http_client.post(
                "/auth/v1/token",
                params={"grant_type": "password"},
                headers=self._default_headers(json_content=True),
                json=payload,
            )
        except httpx.RequestError as exc:  # Network issue
            print("[AuthService] Network error during login:", exc)
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK) from exc

        if response.status_code in (400, 401):
            print("[AuthService] Invalid credentials for", email)
            raise AuthError("Invalid email or password.", AuthErrorCode.INVALID_CREDENTIALS)

        if response.status_code >= 500:
            print("[AuthService] Supabase server error during login:", response.text)
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK)

        if response.status_code != 200:
            print("[AuthService] Unexpected login response:", response.status_code, response.text)
            raise AuthError("Invalid email or password.", AuthErrorCode.INVALID_CREDENTIALS)

        data = response.json()
        session = self._build_session(data)
        user = data.get("user") or {}
        if not user:
            print("[AuthService] Login response missing user payload")
            raise AuthError("Invalid email or password.", AuthErrorCode.INVALID_CREDENTIALS)

        with self._session_lock:
            self._session = session
            self._user = user

        print("[AuthService] Authentication successful for", email)
        return user, self._session_to_dict(session)

    def get_user(self) -> Optional[Dict[str, Any]]:
        """Return the authenticated user if the session is valid."""

        if not self._ensure_session_valid():
            return None

        try:
            response = self._http_client.get(
                "/auth/v1/user",
                headers=self._auth_headers(),
            )
        except httpx.RequestError as exc:
            print("[AuthService] Network error during user fetch:", exc)
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK) from exc

        if response.status_code == 401:
            print("[AuthService] Session expired or invalid while fetching user")
            self.sign_out()
            return None

        if response.status_code != 200:
            print("[AuthService] Unexpected response while fetching user:", response.status_code, response.text)
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK)

        data = response.json()
        with self._session_lock:
            self._user = data.get("user", data)
        return self._user

    def select_own_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's profile row from Supabase REST endpoint."""

        if not self._ensure_session_valid():
            raise AuthError("Invalid email or password.", AuthErrorCode.INVALID_CREDENTIALS)

        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = self._http_client.get(
                    "/rest/v1/user_profiles",
                    headers=self._auth_headers(
                        extra={
                            "Accept": "application/vnd.pgrst.object+json",
                            "Prefer": "return=representation",
                        }
                    ),
                    params={
                        "user_id": f"eq.{user_id}",
                        "select": "user_id,username,is_active,created_at",
                        "limit": "1",
                    },
                )
            except httpx.RequestError as exc:
                print(
                    f"[AuthService] Network error during profile fetch (attempt {attempt + 1}/3):",
                    exc,
                )
                last_exc = exc
                continue

            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    print("[AuthService] Failed to parse profile JSON:", exc)
                    raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK) from exc
                print("[AuthService] Profile fetch succeeded for", user_id)
                if not data:
                    print("[AuthService] Profile payload empty for", user_id)
                    raise AuthError(
                        "Your account is disabled. Contact the owner.",
                        AuthErrorCode.ACCOUNT_DISABLED,
                    )
                return data

            if response.status_code == 404:
                print("[AuthService] Profile missing for", user_id)
                raise AuthError(
                    "Profile missing. Contact the owner.", AuthErrorCode.PROFILE_MISSING
                )

            if response.status_code == 403:
                print("[AuthService] Profile access forbidden for", user_id)
                raise AuthError(
                    "Your account is disabled. Contact the owner.",
                    AuthErrorCode.ACCOUNT_DISABLED,
                )

            if response.status_code in (408, 425, 429, 500, 502, 503, 504):
                print(
                    f"[AuthService] Transient error {response.status_code} during profile fetch, retrying"
                )
                last_exc = AuthError("Network error. Please try again.", AuthErrorCode.NETWORK)
                continue

            print(
                "[AuthService] Unexpected response while fetching profile:",
                response.status_code,
                response.text,
            )
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK)

        if last_exc is not None:
            raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK) from last_exc
        raise AuthError("Network error. Please try again.", AuthErrorCode.NETWORK)

    def sign_out(self) -> None:
        """Invalidate the current session both locally and with Supabase."""

        with self._session_lock:
            session = self._session
            self._session = None
            self._user = None

        if session is None:
            return

        try:
            self._http_client.post(
                "/auth/v1/logout",
                headers=self._auth_headers(extra={"Content-Type": "application/json"}, session=session),
                json={},
            )
        except httpx.RequestError as exc:
            print("[AuthService] Network error during logout:", exc)
        finally:
            print("[AuthService] Session cleared")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_session_valid(self) -> bool:
        with self._session_lock:
            session = self._session
        if session is None:
            return False
        if not session.is_expired:
            return True
        return self._refresh_session()

    def _refresh_session(self) -> bool:
        with self._session_lock:
            session = self._session
        if session is None:
            return False

        try:
            response = self._http_client.post(
                "/auth/v1/token",
                params={"grant_type": "refresh_token"},
                headers=self._default_headers(json_content=True),
                json={"refresh_token": session.refresh_token},
            )
        except httpx.RequestError as exc:
            print("[AuthService] Network error during token refresh:", exc)
            return False

        if response.status_code != 200:
            print(
                "[AuthService] Failed to refresh session:",
                response.status_code,
                response.text,
            )
            return False

        data = response.json()
        new_session = self._build_session(data)
        with self._session_lock:
            self._session = new_session
            if data.get("user"):
                self._user = data["user"]
        print("[AuthService] Session successfully refreshed")
        return True

    def _build_session(self, data: Dict[str, Any]) -> AuthSession:
        expires_in = data.get("expires_in")
        if expires_in is None:
            expires_in = 3600
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=float(expires_in))
        return AuthSession(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
        )

    def _session_to_dict(self, session: AuthSession) -> Dict[str, Any]:
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at.isoformat(),
        }

    def _default_headers(self, json_content: bool = False) -> Dict[str, str]:
        headers = {
            "apikey": self._anon_key,
        }
        if json_content:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
        return headers

    def _auth_headers(
        self,
        *,
        extra: Optional[Dict[str, str]] = None,
        session: Optional[AuthSession] = None,
    ) -> Dict[str, str]:
        with self._session_lock:
            active_session = session or self._session
        if active_session is None:
            raise AuthError("Invalid email or password.", AuthErrorCode.INVALID_CREDENTIALS)
        headers = {
            "Authorization": f"Bearer {active_session.access_token}",
            "apikey": self._anon_key,
        }
        if extra:
            headers.update(extra)
        return headers

    def close(self) -> None:
        self._http_client.close()


__all__ = [
    "AuthError",
    "AuthErrorCode",
    "AuthService",
    "AuthSession",
]
