#!/usr/bin/env python3
"""Опрос клиентов с MAX: трудности с выписками на Госуслугах.

Работает через Supabase REST + MaxBotClient (public.case_chat_outbox
может отсутствовать в PostgREST schema cache на self-host).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _sb():
    from sfrfr.db.session import get_supabase_client

    return get_supabase_client()


def audit() -> dict[str, Any]:
    from sfrfr.services.contact_policy import is_quiet_hours

    sb = _sb()
    out: dict[str, Any] = {
        "quiet_hours": is_quiet_hours(),
        "ts": datetime.now(UTC).isoformat(),
    }

    # outbox presence
    try:
        rows = (
            sb.table("case_chat_outbox")
            .select("id,status")
            .limit(1)
            .execute()
            .data
        )
        out["outbox_rest"] = "ok"
        since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        all_rows = (
            sb.table("case_chat_outbox")
            .select("id,status,attempts,last_error,created_at")
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        out["outbox_7d"] = dict(Counter(r.get("status") for r in all_rows))
        out["outbox_problems"] = [
            {
                "status": r.get("status"),
                "attempts": r.get("attempts"),
                "error": str(r.get("last_error") or "")[:120],
            }
            for r in all_rows
            if r.get("status") in ("pending", "failed")
        ][:30]
    except Exception as exc:  # noqa: BLE001
        out["outbox_rest"] = f"missing:{type(exc).__name__}"
        out["outbox_7d"] = {}
        out["outbox_note"] = (
            "case_chat_outbox недоступен через PostgREST — "
            "доставка через MaxBotClient напрямую после case_messages"
        )

    clients = sb.table("clients").select("id,max_user_id").execute().data or []
    with_max = [
        c for c in clients if str(c.get("max_user_id") or "").strip()
    ]
    out["clients_total"] = len(clients)
    out["clients_with_max"] = len(with_max)

    cases = (
        sb.table("cases")
        .select("id,client_id,is_test,pipeline_status,b2c_status,created_at")
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
        .data
        or []
    )
    out["cases_fetched"] = len(cases)

    since24 = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    try:
        msgs = (
            sb.table("case_messages")
            .select("id,case_id,author_kind,created_at,body")
            .gte("created_at", since24)
            .in_("author_kind", ["staff", "system"])
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        msgs = []
    marked = [m for m in msgs if MARKER in (m.get("body") or "").lower()]
    out["staff_system_24h"] = len(msgs)
    out["survey_marker_24h"] = len(marked)

    # delivered_at may be absent
    undelivered_note = "schema without delivered_at; delivery = MaxBotClient response"
    out["delivery_check"] = undelivered_note
    return out


def _survey_count_48h(sb, case_id: str) -> int:
    since = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    rows = (
        sb.table("case_messages")
        .select("id,body,created_at")
        .eq("case_id", case_id)
        .in_("author_kind", ["staff", "system"])
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    return sum(1 for r in rows if MARKER in (r.get("body") or "").lower())


def list_candidates() -> list[dict[str, Any]]:
    from sfrfr.services.contact_policy import can_contact, is_quiet_hours

    sb = _sb()
    quiet = is_quiet_hours()
    clients = sb.table("clients").select("id,max_user_id").execute().data or []
    cid_to_max = {
        str(c["id"]): str(c.get("max_user_id") or "").strip()
        for c in clients
        if str(c.get("max_user_id") or "").strip()
    }
    cases = (
        sb.table("cases")
        .select("id,client_id,is_test,pipeline_status,b2c_status,created_at")
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
        .data
        or []
    )
    # latest case per client_id first, then dedupe by max_user_id
    latest_by_client: dict[str, dict[str, Any]] = {}
    for case in cases:
        cid = str(case.get("client_id") or "")
        if cid and cid not in latest_by_client:
            latest_by_client[cid] = case

    seen_max: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for cid, case in latest_by_client.items():
        mid = cid_to_max.get(cid, "")
        if not mid or mid in seen_max:
            continue
        seen_max.add(mid)
        item: dict[str, Any] = {
            "case_id": str(case.get("id") or ""),
            "client_id": cid,
            "max_user_id": mid,
            "is_test": bool(case.get("is_test")),
            "pipeline_status": case.get("pipeline_status"),
            "b2c_status": case.get("b2c_status"),
            "action": "send",
            "skip_reason": None,
        }
        if item["is_test"]:
            item["action"] = "skip"
            item["skip_reason"] = "is_test"
            candidates.append(item)
            continue
        if quiet:
            item["action"] = "skip"
            item["skip_reason"] = "quiet_hours"
            candidates.append(item)
            continue
        svc_n = _survey_count_48h(sb, item["case_id"])
        if svc_n >= 1:
            item["action"] = "skip"
            item["skip_reason"] = "duplicate_48h"
            candidates.append(item)
            continue
        decision = can_contact(
            message_type="service",
            channel="max",
            channel_available=True,
            case_archived=False,
            service_messages_last_48h=svc_n,
        )
        if not decision.allowed:
            item["action"] = "skip"
            item["skip_reason"] = decision.reason
            candidates.append(item)
            continue
        candidates.append(item)
    return candidates


def apply_send(
    candidates: list[dict[str, Any]], *, limit: int | None
) -> dict[str, Any]:
    from sfrfr.db.case_messages_write import insert_case_message
    from sfrfr.integrations.max.client import MaxBotClient
    from sfrfr.services.case_chat_delivery import (
        enqueue_max_delivery,
        max_message_id_from_response,
        process_pending_outbox,
    )

    to_send = [c for c in candidates if c["action"] == "send"]
    if limit is not None:
        to_send = to_send[:limit]

    bot = MaxBotClient()
    results: dict[str, Any] = {
        "bot_available": bot.available,
        "sent": 0,
        "queued": 0,
        "failed": 0,
        "details": [],
    }
    if not bot.available:
        results["error"] = "MAX bot unavailable (MAX_BOT_TOKEN?)"
        return results

    outbox_ok = True
    try:
        _sb().table("case_chat_outbox").select("id").limit(1).execute()
    except Exception:  # noqa: BLE001
        outbox_ok = False
    results["outbox_available"] = outbox_ok

    for item in to_send:
        case_id = item["case_id"]
        max_uid = item["max_user_id"]
        try:
            message_row = insert_case_message(
                {
                    "case_id": case_id,
                    "author_kind": "system",
                    "body": MESSAGE_BODY,
                    "channel_origin": "admin",
                }
            )
            message_id = str(message_row.get("id") or "").strip() or None

            delivered = False
            if outbox_ok:
                queued = enqueue_max_delivery(
                    case_id=case_id,
                    message_id=message_id,
                    max_user_id=max_uid,
                    body=MESSAGE_BODY,
                )
                if queued:
                    process_pending_outbox(limit=3)
                    results["queued"] += 1
                    delivered = True
                    results["details"].append(
                        {
                            "case_id": case_id[:8],
                            "status": "queued_outbox",
                            "message_id": message_id,
                        }
                    )

            if not delivered:
                resp = bot.send_message(text=MESSAGE_BODY, user_id=max_uid)
                if isinstance(resp, dict) and (
                    resp.get("skipped") or resp.get("ok") is False or resp.get("error")
                ):
                    results["failed"] += 1
                    results["details"].append(
                        {
                            "case_id": case_id[:8],
                            "status": "send_failed",
                            "resp": str(resp)[:160],
                        }
                    )
                else:
                    ext = max_message_id_from_response(resp)
                    results["sent"] += 1
                    results["details"].append(
                        {
                            "case_id": case_id[:8],
                            "status": "sent_direct",
                            "message_id": message_id,
                            "external_id": ext,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            results["failed"] += 1
            results["details"].append(
                {
                    "case_id": case_id[:8],
                    "status": "error",
                    "error": str(exc)[:200],
                }
            )

    return results


def verify() -> dict[str, Any]:
    sb = _sb()
    since = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    rows = (
        sb.table("case_messages")
        .select("id,case_id,author_kind,created_at,body")
        .gte("created_at", since)
        .eq("author_kind", "system")
        .execute()
        .data
        or []
    )
    marked = [r for r in rows if MARKER in (r.get("body") or "").lower()]
    out: dict[str, Any] = {
        "survey_messages_1h": len(marked),
        "sample_case_ids": [str(r.get("case_id") or "")[:8] for r in marked[:20]],
    }
    try:
        ob = (
            sb.table("case_chat_outbox")
            .select("status")
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        out["outbox_1h"] = dict(Counter(r.get("status") for r in ob))
    except Exception:  # noqa: BLE001
        out["outbox_1h"] = {"unavailable": 1}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="/opt/sfrfr/.env")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    _load_dotenv(Path(args.env_file))
    root = Path(__file__).resolve().parents[1]
    _load_dotenv(root / ".env")

    # Ensure sfrfr imports resolve when run from /opt/sfrfr/scripts
    if str(root) not in sys.path:
        sys.path.insert(0, str(root / "src") if (root / "src").is_dir() else str(root))

    report: dict[str, Any] = {"ts": datetime.now(UTC).isoformat()}

    report["audit"] = audit()
    if args.audit_only:
        _emit(report, args.json_out)
        return 0

    if args.verify and not args.apply and not args.dry_run:
        report["verify"] = verify()
        _emit(report, args.json_out)
        return 0

    candidates = list_candidates()
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
        ][:40],
        "sample_skips": [
            {"case_id": c["case_id"][:8], "reason": c["skip_reason"]}
            for c in candidates
            if c["action"] == "skip"
        ][:40],
    }

    if args.dry_run or not args.apply:
        report["note"] = "dry-run only; pass --apply to send"
        _emit(report, args.json_out)
        return 0

    report["apply"] = apply_send(candidates, limit=args.limit)
    report["verify"] = verify()
    _emit(report, args.json_out)
    return 0


def _emit(report: dict[str, Any], path: str) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if path:
        Path(path).write_text(text, encoding="utf-8")
        print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
