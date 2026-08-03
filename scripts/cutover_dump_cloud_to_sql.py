"""Dump Cloud → SQL via REST + Auth Admin API (no direct PG pooler)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "secrets" / "cutover-dumps" / "cloud_data.sql"

PUBLIC_TABLES = [
    "clients",
    "staff_roles",
    "cases",
    "case_representatives",
    "case_messages",
    "case_pipeline_data",
    "case_knowledge_feedback",
    "checklist_items",
    "documents",
    "communications",
    "consents",
    "contract_acceptances",
    "orders",
    "payments",
    "result_evidence",
    "access_audit",
]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def lit(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False).replace("'", "''")
        return f"'{s}'::jsonb"
    return "'" + str(val).replace("'", "''") + "'"


def http_json(url: str, key: str) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rest_rows(base: str, key: str, table: str) -> list[dict]:
    try:
        data = http_json(f"{base.rstrip('/')}/rest/v1/{table}?select=*", key)
        return data if isinstance(data, list) else []
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code in (404, 406) or "does not exist" in body:
            print("skip", table, e.code, flush=True)
            return []
        raise RuntimeError(f"{table}: {e.code} {body[:300]}") from e


def inserts_for(schema: str, table: str, rows: list[dict]) -> list[str]:
    if not rows:
        return []
    cols = list(rows[0].keys())
    col_sql = ", ".join(f'"{c}"' for c in cols)
    out = []
    for row in rows:
        vals = ", ".join(lit(row.get(c)) for c in cols)
        out.append(f"INSERT INTO {schema}.{table} ({col_sql}) VALUES ({vals});")
    return out


def auth_admin_users(base: str, key: str) -> list[dict]:
    # paginate
    users: list[dict] = []
    page = 1
    per = 50
    while True:
        url = f"{base.rstrip('/')}/auth/v1/admin/users?page={page}&per_page={per}"
        data = http_json(url, key)
        batch = data.get("users", data) if isinstance(data, dict) else data
        if not batch:
            break
        users.extend(batch)
        print("auth page", page, "got", len(batch), flush=True)
        if len(batch) < per:
            break
        page += 1
    return users


def auth_user_inserts(users: list[dict]) -> list[str]:
    """Minimal auth.users + identity rows from Admin API payload."""
    out: list[str] = []
    for u in users:
        uid = u.get("id")
        email = u.get("email")
        if not uid:
            continue
        meta_app = lit(u.get("app_metadata") or {})
        meta_user = lit(u.get("user_metadata") or {})
        created = lit(u.get("created_at"))
        updated = lit(u.get("updated_at") or u.get("created_at"))
        confirmed = lit(u.get("email_confirmed_at") or u.get("confirmed_at"))
        phone_raw = u.get("phone") or None
        if isinstance(phone_raw, str) and not phone_raw.strip():
            phone_raw = None
        phone = lit(phone_raw)
        # encrypted_password not returned by Admin API — users re-auth via magic link / OTP.
        out.append(
            "INSERT INTO auth.users ("
            "instance_id, id, aud, role, email, encrypted_password, "
            "email_confirmed_at, raw_app_meta_data, raw_user_meta_data, "
            "created_at, updated_at, phone, is_super_admin, is_sso_user, is_anonymous"
            ") VALUES ("
            f"'00000000-0000-0000-0000-000000000000'::uuid, '{uid}'::uuid, "
            f"'authenticated', 'authenticated', {lit(email)}, NULL, "
            f"{confirmed}, {meta_app}, {meta_user}, "
            f"{created}::timestamptz, {updated}::timestamptz, {phone}, "
            "FALSE, FALSE, FALSE"
            ");"
        )
        # email identity so GoTrue finds the user
        if email:
            ident = {
                "sub": uid,
                "email": email,
                "email_verified": bool(u.get("email_confirmed_at") or u.get("confirmed_at")),
            }
            out.append(
                "INSERT INTO auth.identities ("
                "provider_id, user_id, identity_data, provider, "
                "last_sign_in_at, created_at, updated_at, id"
                ") VALUES ("
                f"'{uid}', '{uid}'::uuid, {lit(ident)}, 'email', "
                f"{created}::timestamptz, {created}::timestamptz, {updated}::timestamptz, "
                "gen_random_uuid()"
                ");"
            )
    return out


def main() -> None:
    print("start", flush=True)
    env = load_env(ROOT / ".env")
    url = env["SUPABASE_URL"]
    key = env["SUPABASE_SERVICE_ROLE_KEY"]

    parts = [
        "BEGIN;",
        "TRUNCATE TABLE public.clients CASCADE;",
        "TRUNCATE TABLE auth.refresh_tokens CASCADE;",
        "TRUNCATE TABLE auth.sessions CASCADE;",
        "TRUNCATE TABLE auth.identities CASCADE;",
        "TRUNCATE TABLE auth.users CASCADE;",
        "SET session_replication_role = replica;",
    ]

    print("auth admin...", flush=True)
    users = auth_admin_users(url, key)
    print("users", len(users), flush=True)
    parts.extend(auth_user_inserts(users))

    for table in PUBLIC_TABLES:
        print("rest", table, flush=True)
        rows = rest_rows(url, key, table)
        print(" ", len(rows), flush=True)
        parts.extend(inserts_for("public", table, rows))

    parts += ["SET session_replication_role = DEFAULT;", "COMMIT;"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("OK", OUT, OUT.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
