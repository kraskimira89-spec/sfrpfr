#!/usr/bin/env python3
"""Read-only проверка prod: таблицы TZ27–31 и связанные миграции.

Использование (нужен DATABASE_URL prod, секреты не в git):

    .\\.venv\\Scripts\\Activate.ps1
    python scripts/verify_prod_migrations_tz27_31.py

Exit code 0 — все ожидаемые таблицы есть; 1 — есть пропуски.
"""

from __future__ import annotations

import os
import sys

import psycopg

# Карта: issue Tracker → ожидаемые таблицы
CHECKS: dict[str, list[str]] = {
    "SFRFR-17": ["marketing_consents"],
    "SFRFR-18 / FUNNEL-6": ["diagnosis_feedback"],
    "SFRFR-19": ["diagnostic_results", "secure_share_links", "notification_jobs"],
    "SFRFR-20 / FUNNEL-7": [
        "survey_campaigns",
        "survey_responses",
        "survey_action_tokens",
        "survey_suppressions",
    ],
    "SFRFR-21": ["survey_campaigns"],  # idempotency_key — колонка, таблица та же
    "SFRFR-22": ["delivery_events", "contact_delivery_status"],
    "STAZH-1": ["case_tracker_issues"],
    "MAX-first Sprint 1": ["secure_action_links"],
}

MIGRATION_VERSIONS = [
    "20260823150000",
    "20260823180000",
    "20260823190000",
    "20260823200000",
    "20260823210000",
    "20260823220000",
    "20260823230000",
    "20260823240000",
    "20260825140000",
]


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        print("ERROR: задайте DATABASE_URL (prod read-only)", file=sys.stderr)
        return 2

    missing: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for label, tables in CHECKS.items():
                for table in tables:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                        """,
                        (table,),
                    )
                    if cur.fetchone() is None:
                        missing.append(f"{label}: {table}")

            cur.execute(
                """
                SELECT version FROM supabase_migrations.schema_migrations
                WHERE version = ANY(%s)
                ORDER BY version
                """,
                (MIGRATION_VERSIONS,),
            )
            applied = [row[0] for row in cur.fetchall()]

    print("=== TZ27–31 / STAZH / MAX-first: таблицы ===")
    if missing:
        for item in missing:
            print(f"MISSING  {item}")
    else:
        print("OK  все ожидаемые таблицы на месте")

    print("\n=== schema_migrations (выборка 20260823*) ===")
    if applied:
        for v in applied:
            print(f"  {v}")
    else:
        print("  (ни одна из версий 20260823* не применена)")

    print(f"\nИтого пропусков таблиц: {len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
