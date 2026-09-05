#!/usr/bin/env python3
"""Audit + gosuslugi outreach via MAX (case chat outbox)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MESSAGE_BODY = (
    "Здравствуйте!\n\n"
    "Подскажите, пожалуйста: получилось ли заказать выписку "
    "(ИЛС / сведения о стаже) на Госуслугах?\n"
    "Если на каком-то шаге застряли или не получается скачать PDF — "
    "напишите, разберём по одному шагу.\n\n"
    "Документы удобнее загружать в кабинете («Мои документы») "
    "или прислать файлом в этот чат.\n"
    "Мы готовим документы и план — подаёте через Госуслуги или СФР вы сами."
)

MARKER = "получилось ли заказать выписку"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _dsn() -> str:
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise SystemExit("DATABASE_URL missing")
    return dsn.replace("postgresql+psycopg://", "postgresql://")


def _connect():
    import psycopg

    dsn = _dsn()
    parsed = urlparse(dsn)
    print(f"db host={parsed.hostname} port={parsed.port}", flush=True)
    return psycopg.connect(dsn, connect_timeout=20)


def audit(conn) -> dict[str, Any]:
    from sfrfr.services.contact_policy import is_quiet_hours

    out: dict[str, Any] = {"quiet_hours": is_quiet_hours()}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name IN (
              'case_chat_outbox', 'case_messages', 'clients', 'cases'
            )
            ORDER BY 1, 2
            """
        )
        out["tables"] = [f"{a}.{b}" for a, b in cur.fetchall()]

        if "public.case_chat_outbox" in out["tables"]:
            cur.execute(
                """
                SELECT status, count(*)::int
                FROM public.case_chat_outbox
                WHERE created_at > now() - interval '7 days'
                GROUP BY status
                ORDER BY status
                """
            )
            out["outbox_7d"] = {str(s): int(n) for s, n in cur.fetchall()}
            cur.execute(
                """
                SELECT status, attempts, left(coalesce(last_error,''), 120),
                       case_id::text, created_at
                FROM public.case_chat_outbox
                WHERE status IN ('pending', 'failed')
                  AND created_at > now() - interval '7 days'
                ORDER BY created_at DESC
                LIMIT 30
                """
            )
            out["outbox_problems"] = [
                {
                    "status": r[0],
                    "attempts": r[1],
                    "error": r[2],
                    "case_id": r[3][:8] if r[3] else None,
                    "created_at": r[4].isoformat() if r[4] else None,
                }
                for r in cur.fetchall()
            ]
        else:
            out["outbox_7d"] = {}
            out["outbox_problems"] = []
            out["outbox_missing"] = True

        cur.execute(
            """
            SELECT count(*)::int FROM public.clients
            WHERE nullif(trim(max_user_id), '') IS NOT NULL
            """
        )
        out["clients_with_max"] = int(cur.fetchone()[0])

        cur.execute(
            """
            WITH ranked AS (
              SELECT
                c.id AS case_id,
                c.client_id,
                cl.max_user_id,
                coalesce(c.is_test, false) AS is_test,
                c.pipeline_status,
                c.b2c_status,
                c.created_at,
                row_number() OVER (
                  PARTITION BY cl.max_user_id
                  ORDER BY c.created_at DESC NULLS LAST
                ) AS rn
              FROM public.cases c
              JOIN public.clients cl ON cl.id = c.client_id
              WHERE nullif(trim(cl.max_user_id), '') IS NOT NULL
            )
            SELECT
              count(*) FILTER (WHERE rn = 1)::int AS dedup_all,
              count(*) FILTER (WHERE rn = 1 AND NOT is_test)::int AS dedup_non_test,
              count(*) FILTER (WHERE rn = 1 AND is_test)::int AS dedup_test
            FROM ranked
            """
        )
        row = cur.fetchone()
        out["dedup_all"] = int(row[0])
        out["dedup_non_test"] = int(row[1])
        out["dedup_test"] = int(row[2])

    return out


def _service_count_48h(conn, case_id: str) -> int:
    with conn.cursor() as cur:
        # outbox sent + staff/system messages as proxy for service touches via MAX
        if _table_exists(conn, "public.case_chat_outbox"):
            cur.execute(
                """
                SELECT count(*)::int FROM public.case_chat_outbox
                WHERE case_id = %s::uuid
                  AND status = 'sent'
                  AND sent_at > now() - interval '48 hours'
                """,
                (case_id,),
            )
            n_out = int(cur.fetchone()[0])
        else:
            n_out = 0
        cur.execute(
            """
            SELECT count(*)::int FROM public.case_messages
            WHERE case_id = %s::uuid
              AND author_kind IN ('staff', 'system')
              AND created_at > now() - interval '48 hours'
              AND body ILIKE %s
            """,
            (case_id, f"%{MARKER}%"),
        )
        n_same = int(cur.fetchone()[0])
        return max(n_out, n_same)


def _table_exists(conn, qualified: str) -> bool:
    schema, _, name = qualified.partition(".")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, name),
        )
        return cur.fetchone() is not None


def _already_sent_survey(conn, case_id: str, *, hours: float = 24.0) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM public.case_messages
            WHERE case_id = %s::uuid
              AND author_kind IN ('staff', 'system')
              AND body ILIKE %s
              AND created_at > now() - (%s || ' hours')::interval
            LIMIT 1
            """,
            (case_id, f"%{MARKER}%", str(hours)),
        )
        return cur.fetchone() is not None


def list_candidates(conn) -> list[dict[str, Any]]:
    from sfrfr.services.contact_policy import can_contact, is_quiet_hours

    quiet = is_quiet_hours()
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ranked AS (
              SELECT
                c.id AS case_id,
                c.client_id,
                trim(cl.max_user_id) AS max_user_id,
                coalesce(c.is_test, false) AS is_test,
                c.pipeline_status,
                c.b2c_status,
                c.created_at,
                row_number() OVER (
                  PARTITION BY trim(cl.max_user_id)
                  ORDER BY c.created_at DESC NULLS LAST
                ) AS rn
              FROM public.cases c
              JOIN public.clients cl ON cl.id = c.client_id
              WHERE nullif(trim(cl.max_user_id), '') IS NOT NULL
            )
            SELECT case_id::text, client_id::text, max_user_id,
                   is_test, pipeline_status, b2c_status, created_at
            FROM ranked
            WHERE rn = 1
            ORDER BY created_at DESC NULLS LAST
            """
        )
        rows = cur.fetchall()

    candidates: list[dict[str, Any]] = []
    for case_id, client_id, max_uid, is_test, pipeline, b2c, created_at in rows:
        item: dict[str, Any] = {
            "case_id": case_id,
            "client_id": client_id,
            "max_user_id": max_uid,
            "is_test": bool(is_test),
            "pipeline_status": pipeline,
            "b2c_status": b2c,
            "created_at": created_at.isoformat() if created_at else None,
            "action": "send",
            "skip_reason": None,
        }
        if is_test:
            item["action"] = "skip"
            item["skip_reason"] = "is_test"
            candidates.append(item)
            continue
        if quiet:
            item["action"] = "skip"
            item["skip_reason"] = "quiet_hours"
            candidates.append(item)
            continue
        if _already_sent_survey(conn, case_id, hours=24.0):
            item["action"] = "skip"
            item["skip_reason"] = "duplicate_24h"
            candidates.append(item)
            continue
        svc_n = _service_count_48h(conn, case_id)
        # For this outreach: closed cases ARE allowed (plan 1C).
        # Do not set case_archived. Rate limit by same survey / outbox sent.
        decision = can_contact(
            message_type="service",
            channel="max",
            channel_available=True,
            case_archived=False,
            service_messages_last_48h=svc_n if svc_n else 0,
        )
        # If only generic staff messages in 48h, still allow ONE gosuslugi ask
        # unless the same survey already went (handled above) OR outbox sent >=1
        # with our marker via messages. Re-check: MAX_SERVICE_PER_48H=1 is strict.
        # Plan says respect can_contact. If svc_n >=1 from ANY outbox sent, skip.
        if not decision.allowed:
            # Soften: only skip rate limit if we already sent THIS survey or
            # any outbox in 48h — already counted. Keep policy.
            item["action"] = "skip"
            item["skip_reason"] = decision.reason
            candidates.append(item)
            continue
        candidates.append(item)
    return candidates


def apply_send(conn, candidates: list[dict[str, Any]], *, limit: int | None) -> dict[str, Any]:
    from sfrfr.db.case_messages_write import insert_case_message
    from sfrfr.db.session import get_supabase_client
    from sfrfr.services.case_chat_delivery import (
        enqueue_max_delivery,
        process_pending_outbox,
    )

    to_send = [c for c in candidates if c["action"] == "send"]
    if limit is not None:
        to_send = to_send[:limit]

    results = {"queued": 0, "failed": 0, "details": []}
    sb = get_supabase_client()

    for item in to_send:
        case_id = item["case_id"]
        max_uid = item["max_user_id"]
        try:
            # Prefer PostgREST insert; fallback SQL if needed
            message_row = insert_case_message(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "body": MESSAGE_BODY,
                    "channel_origin": "admin",
                }
            )
            message_id = str(message_row.get("id") or "").strip() or None
            ok = enqueue_max_delivery(
                case_id=case_id,
                message_id=message_id,
                max_user_id=max_uid,
                body=MESSAGE_BODY,
            )
            if not ok:
                # direct SQL outbox if table exists but REST cache stale
                ok = _enqueue_sql(conn, case_id, message_id, max_uid, MESSAGE_BODY)
            if ok:
                results["queued"] += 1
                results["details"].append(
                    {"case_id": case_id[:8], "status": "queued", "message_id": message_id}
                )
            else:
                results["failed"] += 1
                results["details"].append(
                    {"case_id": case_id[:8], "status": "enqueue_failed"}
                )
        except Exception as exc:  # noqa: BLE001
            results["failed"] += 1
            results["details"].append(
                {"case_id": case_id[:8], "status": "error", "error": str(exc)[:160]}
            )

    # Drain outbox via REST if available, else SQL+bot
    drained = 0
    try:
        drained = process_pending_outbox(limit=max(20, results["queued"] + 5))
    except Exception as exc:  # noqa: BLE001
        results["drain_rest_error"] = str(exc)[:160]
        drained = _drain_sql(conn, limit=max(20, results["queued"] + 5))
    results["drained"] = drained
    # refresh schema: unused sb keep for side effects
    _ = sb
    return results


def _enqueue_sql(
    conn, case_id: str, message_id: str | None, max_uid: str, body: str
) -> bool:
    if not _table_exists(conn, "public.case_chat_outbox"):
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.case_chat_outbox
              (case_id, message_id, max_user_id, body, attachments, status)
            VALUES (%s::uuid, %s::uuid, %s, %s, '[]'::jsonb, 'pending')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (case_id, message_id, max_uid, body[:4000]),
        )
        row = cur.fetchone()
    conn.commit()
    return bool(row) or True


def _drain_sql(conn, *, limit: int = 20) -> int:
    """Fallback drain when PostgREST has no outbox in schema cache."""
    if not _table_exists(conn, "public.case_chat_outbox"):
        return 0
    from sfrfr.integrations.max.client import MaxBotClient
    from sfrfr.services.case_chat_delivery import max_message_id_from_response

    bot = MaxBotClient()
    if not bot.available:
        print("MAX bot unavailable", flush=True)
        return 0
    sent = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, case_id, message_id, max_user_id, body, attempts
            FROM public.case_chat_outbox
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        rows = cur.fetchall()
        for oid, case_id, message_id, max_uid, body, attempts in rows:
            try:
                resp = bot.send_message(text=body, user_id=str(max_uid))
                ext = max_message_id_from_response(resp)
                cur.execute(
                    """
                    UPDATE public.case_chat_outbox
                    SET status='sent', sent_at=now(), last_error=NULL
                    WHERE id=%s
                    """,
                    (oid,),
                )
                if message_id and ext:
                    cur.execute(
                        """
                        UPDATE public.case_messages
                        SET delivered_at=now(), external_message_id=%s
                        WHERE id=%s::uuid
                        """,
                        (str(ext), str(message_id)),
                    )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                att = int(attempts or 0) + 1
                status = "failed" if att >= 5 else "pending"
                cur.execute(
                    """
                    UPDATE public.case_chat_outbox
                    SET attempts=%s, last_error=%s, status=%s
                    WHERE id=%s
                    """,
                    (att, str(exc)[:500], status, oid),
                )
    conn.commit()
    return sent


def verify(conn) -> dict[str, Any]:
    out: dict[str, Any] = {}
    with conn.cursor() as cur:
        if _table_exists(conn, "public.case_chat_outbox"):
            cur.execute(
                """
                SELECT status, count(*)::int
                FROM public.case_chat_outbox
                WHERE created_at > now() - interval '1 hour'
                GROUP BY status
                """
            )
            out["outbox_1h"] = {str(s): int(n) for s, n in cur.fetchall()}
            cur.execute(
                """
                SELECT status, left(coalesce(last_error,''), 120), count(*)::int
                FROM public.case_chat_outbox
                WHERE created_at > now() - interval '1 hour'
                  AND status = 'failed'
                GROUP BY 1, 2
                """
            )
            out["failed_errors"] = [
                {"error": e or "", "count": n} for _, e, n in cur.fetchall()
            ]
        cur.execute(
            """
            SELECT count(*)::int FROM public.case_messages
            WHERE author_kind = 'system'
              AND body ILIKE %s
              AND created_at > now() - interval '1 hour'
            """,
            (f"%{MARKER}%",),
        )
        out["survey_messages_1h"] = int(cur.fetchone()[0])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default="/opt/sfrfr/.env",
        help="Path to .env (VPS default /opt/sfrfr/.env)",
    )
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    _load_dotenv(Path(args.env_file))
    # Also allow local repo .env when run from workspace
    root = Path(__file__).resolve().parents[1]
    _load_dotenv(root / ".env")

    report: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "mode": (
            "audit"
            if args.audit_only
            else "apply"
            if args.apply
            else "verify"
            if args.verify
            else "dry-run"
        ),
    }

    with _connect() as conn:
        report["audit"] = audit(conn)
        if args.audit_only:
            _print_report(report)
            _maybe_write(args.json_out, report)
            return 0

        if args.verify and not args.apply and not args.dry_run:
            report["verify"] = verify(conn)
            _print_report(report)
            _maybe_write(args.json_out, report)
            return 0

        candidates = list_candidates(conn)
        skip_counts = Counter(
            c["skip_reason"] for c in candidates if c["action"] == "skip"
        )
        send_n = sum(1 for c in candidates if c["action"] == "send")
        report["candidates"] = {
            "total": len(candidates),
            "send": send_n,
            "skip": dict(skip_counts),
            "sample_send_case_ids": [
                c["case_id"][:8] for c in candidates if c["action"] == "send"
            ][:30],
            "sample_skips": [
                {"case_id": c["case_id"][:8], "reason": c["skip_reason"]}
                for c in candidates
                if c["action"] == "skip"
            ][:30],
        }

        if args.dry_run or not args.apply:
            report["note"] = "dry-run only; pass --apply to send"
            _print_report(report)
            _maybe_write(args.json_out, report)
            return 0

        report["apply"] = apply_send(conn, candidates, limit=args.limit)
        report["verify"] = verify(conn)
        _print_report(report)
        _maybe_write(args.json_out, report)
    return 0


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def _maybe_write(path: str, report: dict[str, Any]) -> None:
    if not path:
        return
    Path(path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
