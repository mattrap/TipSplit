"""CLI for administrators to manage TipSplit access policies."""
import argparse
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


VALID_STATUSES = {"active", "blocked", "expired"}
VALID_ROLES = {"admin", "manager", "user"}


def build_client() -> Client:
    import os

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in your environment."
        )
    return create_client(url, service_key)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Toggle user/device access policies")
    parser.add_argument("--user-id", required=True, help="Supabase auth user UUID")
    parser.add_argument("--device-id", required=True, help="Device identifier")
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="Desired status for the device",
    )
    parser.add_argument(
        "--role",
        choices=sorted(VALID_ROLES),
        help="Optional role override",
    )
    parser.add_argument(
        "--bump",
        action="store_true",
        help="Bump revocation version so connected clients pick up changes",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    client = build_client()

    payload = {
        "user_id": args.user_id,
        "device_id": args.device_id,
        "status": args.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.role:
        payload["role"] = args.role
    else:
        existing = (
            client.table("access_policies")
            .select("role")
            .eq("user_id", args.user_id)
            .eq("device_id", args.device_id)
            .limit(1)
            .execute()
        )
        data = getattr(existing, "data", None) or []
        if not data:
            raise SystemExit("Existing policy not found; role is required for new entries.")

    if args.bump:
        payload["revocation_version"] = int(time.time())

    response = client.table("access_policies").upsert(payload).execute()
    print("Policy updated:")
    print(getattr(response, "data", None) or response)


if __name__ == "__main__":
    main()
