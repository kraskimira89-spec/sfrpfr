"""Очистка ошибочного префикса [[internal]] у сообщений, ушедших клиенту."""

from __future__ import annotations

import argparse

from sfrfr.db.session import get_supabase_client
from sfrfr.services.case_message_text import strip_internal_staff_prefix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb = get_supabase_client()
    try:
        rows = (
            sb.table("case_messages")
            .select("id, body, author_kind, delivered_at, external_message_id")
            .ilike("body", "[[internal]]%")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = (
            sb.table("case_messages")
            .select("id, body, author_kind")
            .ilike("body", "[[internal]]%")
            .execute()
            .data
            or []
        )
    updated = 0
    for row in rows:
        body = str(row.get("body") or "")
        cleaned = strip_internal_staff_prefix(body)
        if cleaned == body or not cleaned:
            continue
        # Только сообщения, которые могли уйти клиенту (не чисто internal-заметка).
        sent_markers = bool(row.get("delivered_at") or row.get("external_message_id"))
        author = str(row.get("author_kind") or "")
        if author == "system" or sent_markers:
            if args.dry_run:
                print(row["id"], cleaned[:80])
            else:
                sb.table("case_messages").update({"body": cleaned}).eq("id", row["id"]).execute()
            updated += 1
    print(f"OK updated={updated} scanned={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
