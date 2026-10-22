"""Регрессия Postgres 42P10: ON CONFLICT должен матчить partial unique index."""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

_FN_RE = re.compile(
    r"create\s+or\s+replace\s+function\s+private\.enqueue_case_chat_outbox\s*\(\s*\)"
    r".*?\$\$\s*;",
    re.I | re.S,
)

_ON_CONFLICT_RE = re.compile(
    r"on\s+conflict\s*\(\s*message_id\s*\)\s*"
    r"(?:where\s+message_id\s+is\s+not\s+null\s+)?"
    r"do\s+nothing",
    re.I,
)


def _latest_enqueue_function_sql() -> str:
    latest = ""
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for match in _FN_RE.finditer(text):
            latest = match.group(0)
    assert latest, "private.enqueue_case_chat_outbox() не найден в миграциях"
    return latest


def test_enqueue_outbox_on_conflict_matches_partial_unique_index() -> None:
    """Partial uidx case_chat_outbox_message_uidx WHERE message_id IS NOT NULL.

    Bare ON CONFLICT (message_id) → 42P10 на любом INSERT case_messages,
    который триггерит enqueue (channel_origin cabinet/admin/bot).
    """
    fn_sql = _latest_enqueue_function_sql()
    match = _ON_CONFLICT_RE.search(fn_sql)
    assert match, f"ON CONFLICT (message_id) не найден в:\n{fn_sql[-400:]}"
    assert "where message_id is not null" in match.group(0).lower(), (
        "ON CONFLICT без predicate не матчит partial unique index (42P10)"
    )
