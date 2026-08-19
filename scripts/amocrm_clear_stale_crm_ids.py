"""Очистить cases.crm_external_id, если сделка удалена в amo (Lead not found)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
    return env


def amo_lead_exists(base: str, token: str, lead_id: str) -> bool:
    req = urllib.request.Request(
        f"{base}/leads/{lead_id}",
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # amo: 204 = сделка удалена / недоступна
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code in {204, 404}:
            return False
        raise


def main() -> None:
    env_path = Path(os.environ.get("SFRFR_ENV", ROOT / ".env"))
    env = load_dotenv(env_path)
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from supabase import create_client

    sub = os.environ.get("AMO_SUBDOMAIN", "").strip()
    token = os.environ.get("AMO_ACCESS_TOKEN", "").strip()
    if not sub or not token:
        raise SystemExit("AMO_SUBDOMAIN / AMO_ACCESS_TOKEN required")

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    base = f"https://{sub}.amocrm.ru/api/v4"

    cases = (
        sb.table("cases")
        .select("id,crm_external_id")
        .not_.is_("crm_external_id", "null")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
        .data
        or []
    )

    cleared = 0
    for case in cases:
        case_id = str(case.get("id") or "")
        lead_id = str(case.get("crm_external_id") or "").strip()
        if not case_id or not lead_id.isdigit():
            continue
        if amo_lead_exists(base, token, lead_id):
            continue
        sb.table("cases").update({"crm_external_id": None}).eq("id", case_id).execute()
        cleared += 1
        print(json.dumps({"case_id": case_id, "lead_id": lead_id, "cleared": True}, ensure_ascii=False))

    print(f"cleared={cleared}")


if __name__ == "__main__":
    main()
