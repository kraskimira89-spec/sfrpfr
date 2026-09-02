#!/usr/bin/env python3
"""Слить буфер переписки MAX (до создания дела) в case_messages."""

from __future__ import annotations

import argparse

from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.max.case_chat_log import _load_pending, _pending, flush_pending_case_chat


def _latest_case_id_for_max(max_user_id: str) -> str | None:
    sb = get_supabase_client()
    clients = (
        sb.table("clients")
        .select("id")
        .eq("max_user_id", max_user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not clients:
        return None
    client_id = str(clients[0].get("id") or "")
    if not client_id:
        return None
    cases = (
        sb.table("cases")
        .select("id")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not cases:
        return None
    return str(cases[0].get("id") or "") or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-user-id", help="Только этот MAX user id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_pending()
    mids = [args.max_user_id] if args.max_user_id else list(_pending.keys())
    total = 0
    for mid in mids:
        mid = str(mid or "").strip()
        if not mid:
            continue
        pending_count = len(_pending.get(mid, []))
        if not pending_count:
            continue
        case_id = _latest_case_id_for_max(mid)
        if not case_id:
            print(f"skip max={mid}: no case ({pending_count} buffered)")
            continue
        if args.dry_run:
            print(f"would flush max={mid} case={case_id[:8]}… n={pending_count}")
            continue
        n = flush_pending_case_chat(max_user_id=mid, case_id=case_id)
        print(f"flushed max={mid} case={case_id[:8]}… written={n}/{pending_count}")
        total += n
    print(f"OK total_written={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
