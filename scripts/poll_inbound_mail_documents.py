#!/usr/bin/env python3
"""Опрос IMAP INBOX → доп. документы в дело или очередь «Требует привязки».

  .\\.venv\\Scripts\\python.exe scripts/poll_inbound_mail_documents.py --limit 20
  .\\.venv\\Scripts\\python.exe scripts/poll_inbound_mail_documents.py --dry-run

Без opaque SFRFR-DOC — только unbound queue. На Диск не публикует.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("poll_inbound_mail")


def _store_document_fn(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.services.document_upload import store_document

    return store_document(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true", help="Не только unseen")
    args = parser.parse_args()

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.yandex_workspace import (
        fetch_message_for_inbound,
        list_inbox,
    )
    from sfrfr.services.mail_inbound_documents import process_inbound_mail_message

    listed = list_inbox(limit=max(1, min(args.limit, 50)), unseen_only=not args.all)
    if not listed.get("ok"):
        logger.error("list_inbox failed: %s", listed)
        return 1
    messages = list(listed.get("messages") or listed.get("items") or [])
    if not messages:
        print(json.dumps({"ok": True, "processed": 0, "detail": "empty_inbox"}, ensure_ascii=False))
        return 0

    repo = CaseRepository()
    results: list[dict[str, Any]] = []
    for meta in messages:
        if not isinstance(meta, dict):
            continue
        uid = str(meta.get("uid") or "").strip()
        if not uid:
            continue
        fetched = fetch_message_for_inbound(uid)
        if not fetched.get("ok"):
            results.append({"uid": uid, "ok": False, "error": fetched.get("error")})
            continue
        attachments = list(fetched.get("attachments") or [])
        if args.dry_run:
            results.append(
                {
                    "uid": uid,
                    "dry_run": True,
                    "subject": str(fetched.get("subject") or "")[:80],
                    "attachment_names": fetched.get("attachment_names") or [],
                }
            )
            continue
        out = process_inbound_mail_message(
            message_id=str(fetched.get("message_id") or f"uid-{uid}"),
            subject=str(fetched.get("subject") or ""),
            sender=str(fetched.get("from") or ""),
            attachments=attachments,
            known_case_ids=[],
            store_document_fn=_store_document_fn,
            repo=repo,
        )
        results.append({"uid": uid, **out})

    print(
        json.dumps(
            {"ok": True, "processed": len(results), "results": results},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
