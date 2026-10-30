"""End-to-end smoke test against a running, seeded stack.

Usage (from backend/): uv run python scripts/smoke_test.py
Reads DEMO_PASSWORD from the environment or the repository .env; BASE_URL defaults to
http://localhost:8000.
"""

import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV = dotenv_values(REPO_ROOT / ".env")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/") + "/api/v1"
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD") or ENV.get("DEMO_PASSWORD") or ""


def check(condition: bool, message: str) -> None:
    print(("PASS " if condition else "FAIL ") + message)
    if not condition:
        sys.exit(1)


def login(client: httpx.Client, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    check(response.status_code == 200, f"login as {email}")
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        check(client.get("/health/db").status_code == 200, "database ready and migrated")

        admin = login(client, "super.admin@flowguard.example.org")
        email = f"smoke.{uuid.uuid4().hex[:8]}@flowguard.example.org"
        created = client.post(
            "/users",
            headers=admin,
            json={
                "email": email,
                "full_name": "Smoke Test User",
                "role": "scrutiny_officer",
                "password": "smoke-test-password",
            },
        )
        check(created.status_code == 201, "Super Admin creates a user")
        user_id = created.json()["id"]

        changed = client.patch(
            f"/users/{user_id}", headers=admin, json={"role": "regional_officer"}
        )
        check(changed.json().get("role") == "regional_officer", "Super Admin changes the role")

        deactivated = client.post(f"/users/{user_id}/deactivate", headers=admin)
        check(deactivated.json().get("is_active") is False, "Super Admin deactivates the user")

        auditor = login(client, "auditor@flowguard.example.org")
        denied = client.post(f"/users/{user_id}/activate", headers=auditor)
        check(denied.status_code == 403, "Auditor cannot reactivate the user")

        entries = client.get(
            "/audit-logs",
            headers=auditor,
            params={"target_type": "user", "target_id": user_id, "sort": "occurred_at"},
        ).json()["items"]
        actions = [(e["action"], e["outcome"]) for e in entries]
        expected = [
            ("users.create", "success"),
            ("users.update", "success"),
            ("users.deactivate", "success"),
            ("users.activate", "denied"),
        ]
        check(actions == expected, f"audit trail in order: {actions}")
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
