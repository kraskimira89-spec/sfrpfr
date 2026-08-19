"""Дозаполнить ссылки SFRFR/MAX в существующих сделках amo."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sfrfr.integrations.amocrm.fields import (  # noqa: E402
    CASE_ID,
    MAX_DIALOG_URL,
    MAX_USER_ID,
    SFRFR_CASE_URL,
    build_lead_custom_fields,
)
from sfrfr.integrations.amocrm.urls import admin_case_url, max_dialog_url  # noqa: E402


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


def amo_req(base: str, token: str, method: str, path: str, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            body_json = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            body_json = {"raw": raw[:500]}
        return exc.code, body_json


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
    cases = (
        sb.table("cases")
        .select("id,crm_external_id,clients(full_name,preferred_channel,max_user_id)")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )

    base = f"https://{sub}.amocrm.ru/api/v4"
    patched = 0
    for case in cases:
        case_id = str(case.get("id") or "")
        lead_id = case.get("crm_external_id")
        if not case_id or not lead_id:
            continue
        client = case.get("clients") or {}
        if isinstance(client, list):
            client = client[0] if client else {}
        channel = str(client.get("preferred_channel") or "")
        max_uid = client.get("max_user_id")
        is_max = bool(max_uid) or channel in {"max_miniapp", "max_chat", "max"}
        fields = build_lead_custom_fields(
            case_id=case_id,
            case_url=admin_case_url(case_id),
            max_dialog_url=max_dialog_url(case_id) if is_max else None,
            max_user_id=str(max_uid).strip() if max_uid else None,
            pipeline_status="intake",
            channel=channel or None,
        )
        status, body = amo_req(
            base,
            token,
            "PATCH",
            "/leads",
            [{"id": int(lead_id), "custom_fields_values": fields}],
        )
        ok = 200 <= status < 300
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "lead_id": lead_id,
                    "ok": ok,
                    "status": status,
                    "has_admin": bool(admin_case_url(case_id)),
                    "has_max_dialog": bool(max_dialog_url(case_id)) if is_max else False,
                },
                ensure_ascii=False,
            )
        )
        if ok:
            patched += 1
        else:
            print(json.dumps(body, ensure_ascii=False)[:400])

    print(f"patched={patched}")


if __name__ == "__main__":
    main()
