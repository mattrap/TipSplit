import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

from version import APP_VERSION

# Load Supabase credentials from the bundled supabase.env first, then fall back to .env
_SUPABASE_ENV_PATH = Path(
    getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
) / "supabase.env"
load_dotenv(_SUPABASE_ENV_PATH)
load_dotenv()


class AccessError(Exception):
    """Base exception for access controller failures."""


class AccessRevoked(AccessError):
    """Raised when access has been revoked or is otherwise unavailable."""


@dataclass
class AccessState:
    user_id: str
    email: str
    role: str
    revocation_version: int


class AccessController:
    """Handle remote authentication and policy enforcement via Supabase."""

    HEARTBEAT_INTERVAL = 45

    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise AccessError(
                "Supabase credentials are not configured. "
                "Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in your environment."
            )

        self._client: Client = create_client(url, key)

        self._session = None
        self._user = None
        self._state: Optional[AccessState] = None
        self._last_revocation_version: Optional[int] = None

        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_callback: Optional[Callable[[str], None]] = None
        self._heartbeat_widget = None

    # ------------------------------------------------------------------
    # Authentication & policy checks
    # ------------------------------------------------------------------
    def sign_in(self, email: str, password: str) -> AccessState:
        if not email or not password:
            raise AccessError("Email and password are required.")

        try:
            response = self._client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:  # pragma: no cover - supabase client handles errors
            raise AccessError(f"Authentication failed: {exc}") from exc

        user = getattr(response, "user", None)
        session = getattr(response, "session", None)
        user_id = _extract_attr(user, "id")
        if not user_id:
            raise AccessError("Authentication response did not include a user id.")

        self._session = session
        self._user = user
        self._last_revocation_version = None
        if session is not None:
            token = _extract_attr(session, "access_token")
            if token:
                self._client.postgrest.auth(token)

        state = self.check_policy_once(user_id=user_id, email=email)
        self._state = state
        return state

    def check_policy_once(
        self,
        *,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> AccessState:
        if user_id is None:
            if self._state is None:
                raise AccessError("No authenticated user available for policy checks.")
            user_id = self._state.user_id
        if email is None:
            if self._state is not None:
                email = self._state.email
            else:
                email = ""

        flags = self._fetch_control_flags()
        self._enforce_control_flags(flags)

        policy = self._fetch_policy(user_id)
        state = self._enforce_policy(policy, user_id=user_id, email=email)
        self._state = state
        return state

    # ------------------------------------------------------------------
    # Heartbeat management
    # ------------------------------------------------------------------
    def start_heartbeat(
        self,
        on_revoke: Callable[[str], None],
        *,
        tk_widget=None,
        interval: Optional[int] = None,
    ) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._heartbeat_callback = on_revoke
        self._heartbeat_widget = tk_widget
        heartbeat_interval = interval or self.HEARTBEAT_INTERVAL

        def runner():
            while not self._stop_event.wait(heartbeat_interval):
                try:
                    self.check_policy_once()
                except AccessRevoked as exc:
                    self._schedule_callback(str(exc))
                    break
                except Exception as exc:  # pragma: no cover - defensive logging
                    print(f"[AccessController] Heartbeat error: {exc}")

        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(target=runner, daemon=True)
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._heartbeat_thread
        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2)
        self._heartbeat_thread = None
        self._heartbeat_callback = None
        self._heartbeat_widget = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _schedule_callback(self, message: str) -> None:
        callback = self._heartbeat_callback
        widget = self._heartbeat_widget
        self.stop()
        if callback is None:
            return

        if widget is not None:
            try:
                widget.after(0, lambda: callback(message))
                return
            except Exception:
                pass
        callback(message)

    def _fetch_control_flags(self) -> dict:
        try:
            response = (
                self._client.table("control_flags")
                .select("*")
                .eq("id", 1)
                .execute()
            )
        except Exception as exc:
            print(f"[AccessController] Control flags unavailable: {exc}")
            return {}

        data = getattr(response, "data", None) or []
        return data[0] if data else {}

    def _enforce_control_flags(self, flags: dict) -> None:
        if not flags:
            return
        if flags.get("global_lock"):
            raise AccessRevoked("Access temporarily disabled by administrator.")

        min_version = flags.get("min_client_version")
        if min_version and _compare_versions(APP_VERSION, min_version) < 0:
            raise AccessRevoked(
                "A newer version of TipSplit is required. "
                f"Minimum allowed version: {min_version}."
            )

    def _fetch_policy(self, user_id: str) -> dict:
        try:
            response = (
                self._client.table("access_policies")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            data = getattr(response, "data", None) or []
        except Exception as exc:
            print(f"[AccessController] Policy lookup skipped: {exc}")
            data = []

        if not data:
            return {"status": "active"}
        return data[0]

    def _enforce_policy(self, policy: dict, *, user_id: str, email: str) -> AccessState:
        status = (policy or {}).get("status", "active")
        if status == "blocked":
            raise AccessRevoked("Access has been blocked for this account.")
        if status == "expired":
            raise AccessRevoked("Access has expired for this account.")
        if status != "active":
            raise AccessRevoked("Access is not active for this account.")

        expires_at = policy.get("expires_at")
        if expires_at:
            expires_dt = _parse_timestamp(expires_at)
            if expires_dt and expires_dt <= datetime.now(timezone.utc):
                raise AccessRevoked("Access has expired for this account.")

        revocation_version = int((policy or {}).get("revocation_version", 0) or 0)
        if (
            self._last_revocation_version is not None
            and revocation_version != self._last_revocation_version
        ):
            # Version changed — ensure we still have an active status
            if status != "active":
                raise AccessRevoked("Access has been updated by administrator.")
        self._last_revocation_version = revocation_version

        role = (policy or {}).get("role")
        if not role and self._user is not None:
            user_metadata = _extract_attr(self._user, "user_metadata") or {}
            role = user_metadata.get("role")
            if not role:
                app_metadata = _extract_attr(self._user, "app_metadata") or {}
                role = app_metadata.get("role")
        role = role or "user"
        return AccessState(
            user_id=user_id,
            email=email,
            role=role,
            revocation_version=revocation_version,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------
    @property
    def role(self) -> Optional[str]:
        return self._state.role if self._state else None

    @property
    def user_id(self) -> Optional[str]:
        return self._state.user_id if self._state else None

    @property
    def email(self) -> Optional[str]:
        return self._state.email if self._state else None


def _extract_attr(obj, attr: str):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(attr)
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(attr)
    if hasattr(obj, "__dict__"):
        return obj.__dict__.get(attr)
    return None


def _parse_timestamp(value: str) -> Optional[datetime]:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except Exception:
        return None


def _compare_versions(current: str, required: str) -> int:
    """Return negative if current < required, zero if equal, positive if newer."""

    def normalize(v: str):
        parts = []
        for chunk in v.replace("-", ".").split("."):
            if chunk.isdigit():
                parts.append(int(chunk))
            else:
                parts.append(chunk)
        return parts

    current_parts = normalize(current)
    required_parts = normalize(required)
    for idx in range(max(len(current_parts), len(required_parts))):
        cur = current_parts[idx] if idx < len(current_parts) else 0
        req = required_parts[idx] if idx < len(required_parts) else 0
        if cur == req:
            continue
        if isinstance(cur, int) and isinstance(req, int):
            return 1 if cur > req else -1
        return 1 if str(cur) > str(req) else -1
    return 0
