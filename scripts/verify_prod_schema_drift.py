#!/usr/bin/env python3
"""Read-only сверка боевой БД (self-host YC) с миграциями репозитория.

Проверяет по объектам в каталоге Postgres (а не только по schema_migrations),
применены ли 15 миграций, которых не было в legacy Supabase Cloud, и выводит
security-сигналы: SECURITY DEFINER в public, rls_auto_enable, RLS без политик,
auth.uid() без (select ...) в marketing_consents_select_own.

Использование (DATABASE_URL боевой БД, секреты не в git):

    .\\.venv\\Scripts\\Activate.ps1
    python scripts/verify_prod_schema_drift.py

Сессия read-only; выводятся только имена объектов, без данных и без DSN.
Exit code 0 — все миграции применены; 1 — есть пропуски; 2 — нет DATABASE_URL.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    checks: tuple[tuple[str, ...], ...]


EXPECTED: tuple[Migration, ...] = (
    Migration("20260727120000", "cases_meeting_url", (("column", "cases", "meeting_url"),)),
    Migration(
        "20260802180000",
        "case_pipeline_analysis_notes",
        (("column", "case_pipeline_data", "analysis_notes"),),
    ),
    Migration(
        "20260804120000",
        "max_intake",
        (("table", "max_intake"), ("index", "max_intake_one_started_per_user_idx")),
    ),
    Migration(
        "20260822180000",
        "cases_next_action",
        (
            ("column", "cases", "next_action"),
            ("column", "cases", "next_action_at"),
            ("column", "cases", "waiting_on"),
            ("constraint", "cases", "cases_waiting_on_check", ""),
        ),
    ),
    Migration(
        "20260822183000",
        "cases_is_test",
        (("column", "cases", "is_test"), ("index", "cases_is_test_idx")),
    ),
    Migration(
        "20260822190000",
        "orders_finance_ops",
        (
            ("column", "orders", "invoice_number"),
            ("column", "orders", "next_action"),
            ("table", "finance_audit"),
            ("index", "orders_invoice_number_uidx"),
        ),
    ),
    Migration(
        "20260829190000",
        "cases_loss_reason",
        (("column", "cases", "loss_reason"), ("column", "cases", "closed_at")),
    ),
    Migration(
        "20260831180000",
        "staff_registration_requests",
        (
            ("table", "staff_registration_requests"),
            ("index", "staff_registration_requests_pending_email_idx"),
        ),
    ),
    Migration(
        "20260902163000",
        "private_case_access_helpers",
        (
            ("function", "private", "is_case_client"),
            ("function", "private", "is_case_representative"),
            ("function", "private", "is_case_staff"),
            ("function", "private", "can_access_case"),
        ),
    ),
    Migration(
        "20260902170000",
        "case_tracker_issues_rls",
        (("policy", "case_tracker_issues", "case_tracker_issues_staff_select"),),
    ),
    Migration(
        "20260902180000",
        "survey_type_acquaint_quality",
        (("constraint", "survey_campaigns", "survey_campaigns_survey_type_check", "acquaint"),),
    ),
    Migration(
        "20260915090000",
        "payments_one_active_per_order",
        (("column", "payments", "created_at"), ("index", "payments_one_active_per_order_uidx")),
    ),
    Migration(
        "20260922120000",
        "case_reactivation_touches",
        (("table", "case_reactivation_touches"),),
    ),
    Migration(
        "20260922130000",
        "client_cookie_consent_once",
        (
            ("column", "clients", "cookie_consent_version"),
            ("column", "clients", "cookie_consent_accepted_at"),
        ),
    ),
    Migration(
        "20260924120000",
        "ocr_source_registry_phase2",
        (
            ("column", "documents", "ocr_source_used"),
            ("column", "document_ingest_jobs", "resolve_trace"),
        ),
    ),
    Migration(
        "20260926150000",
        "consents_evidence_a3",
        (
            ("column", "consents", "text_sha256"),
            ("column", "consents", "max_user_id"),
            ("index", "consents_case_id_idx"),
        ),
    ),
    Migration(
        "20260926170000",
        "questionnaire_b1",
        (
            ("column", "clients", "birth_year"),
            ("column", "cases", "experience_bucket"),
            ("column", "cases", "questionnaire_completed_at"),
        ),
    ),
)

_CHECK_SQL = {
    "table": (
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s"
    ),
    "column": (
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s"
    ),
    "index": "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s",
    "function": (
        "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = %s AND p.proname = %s"
    ),
    "policy": (
        "SELECT 1 FROM pg_policies "
        "WHERE schemaname = 'public' AND tablename = %s AND policyname = %s"
    ),
    "constraint": (
        "SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "WHERE n.nspname = 'public' AND t.relname = %s AND c.conname = %s "
        "AND pg_get_constraintdef(c.oid) LIKE %s"
    ),
}


def _check_present(cur: psycopg.Cursor, check: tuple[str, ...]) -> bool:
    kind, *args = check
    params: tuple[str, ...] = tuple(args)
    if kind == "constraint":
        table, name, needle = args
        params = (table, name, f"%{needle}%")
    cur.execute(_CHECK_SQL[kind], params)
    return cur.fetchone() is not None


def _applied_versions(cur: psycopg.Cursor) -> set[str] | None:
    cur.execute("SELECT to_regclass('supabase_migrations.schema_migrations')")
    row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    cur.execute(
        "SELECT version FROM supabase_migrations.schema_migrations WHERE version = ANY(%s)",
        ([m.version for m in EXPECTED],),
    )
    return {r[0] for r in cur.fetchall()}


def _report_drift(cur: psycopg.Cursor) -> int:
    history = _applied_versions(cur)
    not_applied = 0
    print("=== Миграции: объекты в БД / запись в schema_migrations ===")
    for m in EXPECTED:
        missing = [":".join(c[1:3]) for c in m.checks if not _check_present(cur, c)]
        if not missing:
            status = "OK      "
        elif len(missing) == len(m.checks):
            status = "MISSING "
        else:
            status = "PARTIAL "
        if missing:
            not_applied += 1
        hist = "n/a" if history is None else ("yes" if m.version in history else "no")
        tail = f"  нет: {', '.join(missing)}" if missing else ""
        print(f"{status}{m.version} {m.name}  history={hist}{tail}")
    return not_applied


def _report_security(cur: psycopg.Cursor) -> None:
    print("\n=== Security (read-only) ===")
    cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
    roles = sorted(r[0] for r in cur.fetchall())
    cur.execute(
        "SELECT p.oid, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.prosecdef ORDER BY p.proname"
    )
    for oid, name in cur.fetchall():
        exposed = []
        for role in roles:
            cur.execute("SELECT has_function_privilege(%s, %s::oid, 'EXECUTE')", (role, oid))
            row = cur.fetchone()
            if row and row[0]:
                exposed.append(role)
        flag = "WARN" if exposed else "info"
        print(f"{flag}  SECURITY DEFINER public.{name}  execute: {', '.join(exposed) or '-'}")

    cur.execute(
        "SELECT n.nspname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE p.proname = 'rls_auto_enable'"
    )
    schemas = [r[0] for r in cur.fetchall()]
    print(f"info  rls_auto_enable: {', '.join(schemas) if schemas else 'нет'}")

    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity ORDER BY 1"
    )
    no_rls = [r[0] for r in cur.fetchall()]
    print(f"{'WARN' if no_rls else 'OK  '}  public без RLS: {', '.join(no_rls) or '-'}")

    cur.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity "
        "AND NOT EXISTS (SELECT 1 FROM pg_policies p "
        "WHERE p.schemaname = 'public' AND p.tablename = c.relname) ORDER BY 1"
    )
    no_policy = [r[0] for r in cur.fetchall()]
    print(f"info  RLS без политик ({len(no_policy)}): {', '.join(no_policy) or '-'}")

    cur.execute(
        "SELECT coalesce(qual, '') FROM pg_policies "
        "WHERE schemaname = 'public' AND policyname = 'marketing_consents_select_own'"
    )
    row = cur.fetchone()
    if row is None:
        print("info  marketing_consents_select_own: нет")
    else:
        bare = "auth.uid()" in row[0] and "SELECT auth.uid()" not in row[0]
        print(f"{'WARN' if bare else 'OK  '}  marketing_consents_select_own: "
              f"{'auth.uid() без (select ...)' if bare else 'ok'}")


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("ERROR: задайте DATABASE_URL (боевая БД, read-only)", file=sys.stderr)
        return 2

    with psycopg.connect(dsn) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            not_applied = _report_drift(cur)
            _report_security(cur)

    print(f"\nИтого миграций с пропусками: {not_applied} из {len(EXPECTED)}")
    return 1 if not_applied else 0


if __name__ == "__main__":
    raise SystemExit(main())
