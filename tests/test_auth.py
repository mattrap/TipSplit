import json

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AppConfig import obfuscate_secret, deobfuscate_secret
from auth import AuthManager, AccountStatusError, InvalidCredentialsError

bcrypt = pytest.importorskip("bcrypt")


def test_secret_roundtrip():
    secret = "super-secret-key"
    token = obfuscate_secret(secret)
    assert token != secret
    assert deobfuscate_secret(token) == secret


def test_authenticate_with_cached_data(tmp_path):
    cache_path = tmp_path / "auth_cache.json"
    hashed = bcrypt.hashpw(b"monpassword", bcrypt.gensalt()).decode("utf-8")
    cache_payload = {
        "users": {
            "user@example.com": {
                "email": "user@example.com",
                "password_hash": hashed,
                "status": "active",
                "updated_at": "",
            }
        },
        "last_sync": "2024-01-01T00:00:00Z",
    }
    cache_path.write_text(json.dumps(cache_payload))

    manager = AuthManager(cache_path=str(cache_path))

    result = manager.authenticate("User@example.com", "monpassword")
    assert result.email == "user@example.com"

    with pytest.raises(InvalidCredentialsError):
        manager.authenticate("user@example.com", "wrong")

    manager.cache["users"]["user@example.com"]["status"] = "disabled"
    with pytest.raises(AccountStatusError):
        manager.authenticate("user@example.com", "monpassword")
