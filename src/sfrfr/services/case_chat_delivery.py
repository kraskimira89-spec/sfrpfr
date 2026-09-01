"""Доставка сообщений единого чата: outbox → MAX, уведомления без ПДн."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

CHAT_NOTIFY_NEUTRAL = "В чате по делу есть новое сообщение"

MAX_FILE_REJECT_TEXT = (
    "Спасибо. Для защиты данных файл не добавлен к делу. "
    "Пожалуйста, загрузите его через защищённый личный кабинет."
)

DOCUMENTS_SECTION_LABEL = "Открыть раздел «Мои документы»"


def documents_cabinet_url(case_id: str | None) -> str:
    from sfrfr.integrations.max.intake import cabinet_url_for_case

    base = cabinet_url_for_case(case_id)
    return f"{base}#documents" if case_id else base


def enqueue_max_delivery(
    *,
    case_id: str,
    message_id: str | None,
    max_user_id: str,
    body: str,
) -> None:
    """Поставить сообщение из кабинета в outbox для доставки в MAX."""
    from sfrfr.db.session import get_supabase_client

    mid = str(max_user_id).strip()
    text = (body or "").strip()
    if not mid or not text:
        return
    try:
        get_supabase_client().table("case_chat_outbox").insert(
            {
                "case_id": case_id,
                "message_id": message_id,
                "max_user_id": mid,
                "body": text[:4000],
                "status": "pending",
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("case_chat outbox enqueue failed case=%s: %s", case_id[:8], exc)


def process_pending_outbox(*, limit: int = 20) -> int:
    """Отправить ожидающие сообщения в MAX (best-effort)."""
    from sfrfr.db.session import get_supabase_client
    from sfrfr.integrations.max.client import MaxBotClient

    client = get_supabase_client()
    rows = (
        client.table("case_chat_outbox")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(limit)
        .execute()
        .data
        or []
    )
    if not rows:
        return 0
    bot = MaxBotClient()
    if not bot.available:
        return 0
    sent = 0
    now = datetime.now(UTC).isoformat()
    for row in rows:
        oid = str(row.get("id") or "")
        max_uid = str(row.get("max_user_id") or "").strip()
        body = str(row.get("body") or "").strip()
        message_id = row.get("message_id")
        if not oid or not max_uid or not body:
            continue
        try:
            bot.send_message(text=body, user_id=max_uid)
            client.table("case_chat_outbox").update(
                {
                    "status": "sent",
                    "sent_at": now,
                    "attempts": int(row.get("attempts") or 0) + 1,
                }
            ).eq("id", oid).execute()
            if message_id:
                client.table("case_messages").update({"delivered_at": now}).eq(
                    "id", str(message_id)
                ).execute()
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("case_chat outbox send failed id=%s: %s", oid[:8], exc)
            client.table("case_chat_outbox").update(
                {
                    "status": "failed",
                    "attempts": int(row.get("attempts") or 0) + 1,
                    "last_error": str(exc)[:500],
                }
            ).eq("id", oid).execute()
    return sent


def mirror_client_message_to_max(
    case: dict[str, Any],
    body: str,
    *,
    message_id: str | None = None,
) -> None:
    """Дублировать клиентское сообщение из кабинета в MAX через outbox."""
    client_row = case.get("clients") or {}
    if isinstance(client_row, list):
        client_row = client_row[0] if client_row else {}
    max_uid = str((client_row or {}).get("max_user_id") or "").strip()
    case_id = str(case.get("id") or "").strip()
    if not max_uid or not case_id:
        return
    enqueue_max_delivery(
        case_id=case_id,
        message_id=message_id,
        max_user_id=max_uid,
        body=body,
    )
    process_pending_outbox(limit=5)


def notify_client_new_chat_message(
    *,
    case_id: str,
    max_user_id: str | None,
    preview_body: str | None = None,
) -> None:
    """Нейтральное уведомление в MAX без PII в превью."""
    mid = str(max_user_id or "").strip()
    if not mid:
        return
    # Не дублировать, если текст уже нейтральный системный.
    if (preview_body or "").strip() == CHAT_NOTIFY_NEUTRAL:
        return
    try:
        from sfrfr.integrations.max.client import MaxBotClient

        bot = MaxBotClient()
        if not bot.available:
            return
        bot.send_message(text=CHAT_NOTIFY_NEUTRAL, user_id=mid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat notify MAX failed case=%s: %s", case_id[:8], exc)


def find_message_by_external_id(external_message_id: str) -> dict[str, Any] | None:
    ext = (external_message_id or "").strip()
    if not ext:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("id, case_id")
            .eq("external_message_id", ext)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.info("external_message_id lookup skipped: %s", exc)
        return None


def mark_messages_read_for_client(case_id: str) -> None:
    """Отметить входящие для клиента сообщения прочитанными."""
    try:
        from sfrfr.db.session import get_supabase_client

        now = datetime.now(UTC).isoformat()
        get_supabase_client().table("case_messages").update({"read_at_client": now}).eq(
            "case_id", case_id
        ).in_("author_kind", ["staff", "system", "expert", "operator"]).is_(
            "read_at_client", "null"
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("mark client read skipped case=%s: %s", case_id[:8], exc)


def mark_messages_read_for_staff(case_id: str) -> None:
    """Отметить клиентские сообщения прочитанными для специалиста."""
    try:
        from sfrfr.db.session import get_supabase_client

        now = datetime.now(UTC).isoformat()
        get_supabase_client().table("case_messages").update({"read_at_staff": now}).eq(
            "case_id", case_id
        ).in_("author_kind", ["client", "representative"]).is_(
            "read_at_staff", "null"
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("mark staff read skipped case=%s: %s", case_id[:8], exc)
