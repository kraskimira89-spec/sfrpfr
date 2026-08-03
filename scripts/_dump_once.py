"""Dump Cloud → SQL via REST (public) + explicit-column auth dumps."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

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

# Explicit cols — avoid SELECT * (pooler kills some auth queries).
AUTH_USERS_COLS = [
    "instance_id",
    "id",
    "aud",
    "role",
    "email",
    "encrypted_password",
    "email_confirmed_at",
    "invited_at",
    "confirmation_token",
    "confirmation_sent_at",
    "recovery_token",
    "recovery_sent_at",
    "email_change_token_new",
    "email_change",
    "email_change_sent_at",
    "last_sign_in_at",
    "raw_app_meta_data",
    "raw_user_meta_data",
    "is_super_admin",
    "created_at",
    "updated_at",
    "phone",
    "phone_confirmed_at",
    "phone_change",
    "phone_change_token",
    "phone_change_sent_at",
    "email_change_token_current",
    "email_change_confirm_status",
    "banned_until",
    "reauthentication_token",
    "reauthentication_sent_at",
    "is_sso_user",
    "deleted_at",
    "is_anonymous",
]

AUTH_IDENTITIES_COLS = [
    "provider_id",
    "user_id",
    "identity_data",
    "provider",
    "last_sign_in_at",
    "created_at",
    "updated_at",
    "email",
    "id",
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
    s = str(val).replace("'", "''")
    # uuid / timestamptz as text cast by PG on insert when typed cols exist
    return f"'{s}'"


def inserts_for(schema: str, table: str, rows: list[dict], cols: list[str] | None = None) -> list[str]:
    if not rows:
        return []
    use_cols = cols or list(rows[0].keys())
    col_sql = ", ".join(f'"{c}"' for c in use_cols)
    out = []
    for row in rows:
        vals = ", ".join(lit(row.get(c)) for c in use_cols)
        out.append(f"INSERT INTO {schema}.{table} ({col_sql}) VALUES ({vals});")
    return out


def rest_rows(url: str, key: str, table: str) -> list[dict]:
    endpoint = f"{url.rstrip('/')}/rest/v1/{table}?select=*"
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code in (404, 406) or "does not exist" in body:
            print("skip rest", table, e.code, flush=True)
            return []
        raise RuntimeError(f"REST {table}: {e.code} {body[:300]}") from e


def dump_auth(dsn: str) -> list[str]:
    conn = psycopg.connect(dsn, connect_timeout=30, row_factory=dict_row)
    out: list[str] = []
    cols_sql = ", ".join(AUTH_USERS_COLS)
    with conn.cursor() as cur:
        cur.execute("select id, email from auth.users")
        ids = [r["id"] for r in cur.fetchall()]
        print("auth.users", len(ids), flush=True)
        for uid in ids:
            cur.execute(
                f"select {cols_sql} from auth.users where id = %s",
                (uid,),
            )
            row = cur.fetchone()
            if row:
                out.extend(inserts_for("auth", "users", [dict(row)], AUTH_USERS_COLS))
        cur.execute(
            "select 1 from information_schema.tables where table_schema='auth' and table_name='identities'"
        )
        if cur.fetchone():
            # discover available cols
            cur.execute(
                "select column_name from information_schema.columns "
                "where table_schema='auth' and table_name='identities'"
            )
            have = {r["column_name"] for r in cur.fetchall()}
            cols = [c for c in AUTH_IDENTITIES_COLS if c in have]
            cur.execute("select id, user_id from auth.identities")
            idents = cur.fetchall()
            print("auth.identities", len(idents), flush=True)
            col_sql = ", ".join(cols)
            for ident in idents:
                cur.execute(
                    f"select {col_sql} from auth.identities where id = %s",
                    (ident["id"],),
                )
                row = cur.fetchone()
                if row:
                    out.extend(inserts_for("auth", "identities", [dict(row)], cols))
    conn.close()
    return out


def main() -> None:
    print("start", flush=True)
    env = load_env(ROOT / ".env")
    url = env["SUPABASE_URL"]
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    dsn = dsn.replace(":5432/", ":6543/")
    dsn = re.sub(r"sslmode=[^&]*", "sslmode=require", dsn)

    parts = [
        "BEGIN;",
        "TRUNCATE TABLE public.clients CASCADE;",
        "TRUNCATE TABLE auth.refresh_tokens CASCADE;",
        "TRUNCATE TABLE auth.sessions CASCADE;",
        "TRUNCATE TABLE auth.identities CASCADE;",
        "TRUNCATE TABLE auth.users CASCADE;",
        "SET session_replication_role = replica;",
    ]
    print("auth...", flush=True)
    parts.extend(dump_auth(dsn))
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
