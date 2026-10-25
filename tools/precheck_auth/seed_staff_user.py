"""Создаёт синтетического staff-пользователя в изолированном GoTrue.

ENV:
  PRECHECK_AUTH_URL
  PRECHECK_AUTH_SERVICE_KEY
  PRECHECK_AUTH_STAFF_EMAIL (default staff-e2e@precheck.local)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = (os.environ.get("PRECHECK_AUTH_URL") or "").rstrip("/")
    service = (os.environ.get("PRECHECK_AUTH_SERVICE_KEY") or "").strip()
    email = (os.environ.get("PRECHECK_AUTH_STAFF_EMAIL") or "staff-e2e@precheck.local").strip()
    if not base or not service:
        print(
            "BLOCKED: set PRECHECK_AUTH_URL and PRECHECK_AUTH_SERVICE_KEY (run up.ps1)",
            flush=True,
        )
        return 2

    body = json.dumps(
        {
            "email": email,
            "email_confirm": True,
            "user_metadata": {"role": "staff", "precheck_e2e": True},
            "app_metadata": {"provider": "email", "providers": ["email"]},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/admin/users",
        data=body,
        headers={
            "Authorization": f"Bearer {service}",
            "apikey": service,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            print(raw, flush=True)
            return 0
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {raw[:500]}", flush=True)
        # already exists → ok for idempotent seed
        if exc.code in {422, 400} and "already" in raw.lower():
            return 0
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED: {type(exc).__name__}", flush=True)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
