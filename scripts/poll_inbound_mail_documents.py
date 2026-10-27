#!/usr/bin/env python3
"""Опрос IMAP INBOX → доп. документы в дело или очередь «Требует привязки».

Защита от параллельного запуска: file lock.
Письмо помечается обработанным только после надёжного save/queue.
Повторный опрос не создаёт дубли (MailInboundProcessedStore + Unbound dedup).

  .\\.venv\\Scripts\\python.exe scripts/poll_inbound_mail_documents.py --limit 20
  .\\.venv\\Scripts\\python.exe scripts/poll_inbound_mail_documents.py --dry-run
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


def _lock_path() -> Path:
    from sfrfr.services.extra_document_intake import default_mail_processed_root

    root = default_mail_processed_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / "poll.lock"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true", help="Не только unseen")
    args = parser.parse_args()

    lock_file = _lock_path()
    try:
        lock_fd = open(lock_file, "a+", encoding="utf-8")
    except OSError as exc:
        logger.error("lock open failed: %s", exc)
        return 1

    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                print(json.dumps({"ok": False, "error": "already_running"}, ensure_ascii=False))
                return 0
        else:
            import fcntl

            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                print(json.dumps({"ok": False, "error": "already_running"}, ensure_ascii=False))
                return 0

        return _run(args)
    finally:
        try:
            lock_fd.close()
        except OSError:
            pass


def _run(args: argparse.Namespace) -> int:
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.yandex_workspace import (
        fetch_message_for_inbound,
        list_inbox,
    )
    from sfrfr.services.extra_document_intake import MailInboundProcessedStore
    from sfrfr.services.mail_inbound_documents import process_inbound_mail_message

    processed_store = MailInboundProcessedStore()
    listed = list_inbox(limit=max(1, min(args.limit, 50)), unseen_only=not args.all)
    if not listed.get("ok"):
        logger.error("list_inbox failed: %s", listed)
        return 1
    messages = list(listed.get("items") or [])
    if not messages:
        processed_store.record_poll_success(processed=0, skipped=0)
        print(json.dumps({"ok": True, "processed": 0, "detail": "empty_inbox"}, ensure_ascii=False))
        return 0

    repo = CaseRepository()
    results: list[dict[str, Any]] = []
    skipped = 0
    done = 0
    for meta in messages:
        if not isinstance(meta, dict):
            continue
        uid = str(meta.get("uid") or "").strip()
        mid_hint = str(meta.get("message_id") or "").strip()
        if mid_hint and processed_store.is_processed(mid_hint):
            skipped += 1
            results.append({"uid": uid, "skipped": True, "reason": "already_processed"})
            continue
        if not uid:
            continue
        fetched = fetch_message_for_inbound(uid)
        if not fetched.get("ok"):
            results.append({"uid": uid, "ok": False, "error": fetched.get("error")})
            continue
        mid = str(fetched.get("message_id") or mid_hint or f"uid-{uid}").strip()
        if processed_store.is_processed(mid):
            skipped += 1
            results.append({"uid": uid, "skipped": True, "reason": "already_processed"})
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
            message_id=mid,
            subject=str(fetched.get("subject") or ""),
            sender=str(fetched.get("from") or ""),
            attachments=attachments,
            known_case_ids=[],
            store_document_fn=_store_document_fn,
            repo=repo,
            processed_store=processed_store,
        )
        if out.get("ok"):
            done += 1
        results.append({"uid": uid, **out})

    if not args.dry_run:
        processed_store.record_poll_success(processed=done, skipped=skipped)
    last = processed_store.last_success()
    print(
        json.dumps(
            {
                "ok": True,
                "processed": done,
                "skipped": skipped,
                "results": results,
                "last_success": last,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
