"""Доставка сообщений единого чата: outbox → MAX, уведомления без ПДн."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

CHAT_NOTIFY_NEUTRAL = "В чате по делу есть новое сообщение"
CHAT_ACTIVITY_TTL_SECONDS = 90
MAX_DELIVERY_ATTEMPTS = 5

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
    attachments: list[dict[str, Any]] | None = None,
) -> bool:
    """Поставить сообщение из кабинета в outbox для доставки в MAX."""
    from sfrfr.db.session import get_supabase_client

    mid = str(max_user_id).strip()
    text = (body or "").strip()
    if not mid or not text:
        return False
    if message_id:
        try:
            existing = (
                get_supabase_client()
                .table("case_chat_outbox")
                .select("id, attachments, status")
                .eq("message_id", str(message_id))
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                if attachments:
                    get_supabase_client().table("case_chat_outbox").update(
                        {"attachments": attachments}
                    ).eq("id", str(existing[0].get("id") or "")).eq(
                        "status", "pending"
                    ).execute()
                return True
        except Exception:  # noqa: BLE001 — таблица может быть ещё не накатана
            pass
    try:
        get_supabase_client().table("case_chat_outbox").insert(
            {
                "case_id": case_id,
                "message_id": message_id,
                "max_user_id": mid,
                "body": text[:4000],
                "attachments": attachments or [],
                "status": "pending",
            }
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        if message_id:
            try:
                existing = (
                    get_supabase_client()
                    .table("case_chat_outbox")
                    .select("id, attachments, status")
                    .eq("message_id", str(message_id))
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if existing:
                    if attachments:
                        get_supabase_client().table("case_chat_outbox").update(
                            {"attachments": attachments}
                        ).eq("id", str(existing[0].get("id") or "")).eq(
                            "status", "pending"
                        ).execute()
                    return True
            except Exception:  # noqa: BLE001
                pass
        logger.warning("case_chat outbox enqueue failed case=%s: %s", case_id[:8], exc)
        return False


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
        attachments = row.get("attachments")
        if not oid or not max_uid or not body:
            continue
        try:
            send_kwargs: dict[str, Any] = {"text": body, "user_id": max_uid}
            if isinstance(attachments, list) and attachments:
                send_kwargs["attachments"] = attachments
            result = bot.send_message(**send_kwargs)
            if isinstance(result, dict) and (result.get("skipped") or result.get("ok") is False):
                raise RuntimeError(str(result.get("reason") or "MAX delivery skipped"))
            client.table("case_chat_outbox").update(
                {
                    "status": "sent",
                    "sent_at": now,
                    "attempts": int(row.get("attempts") or 0) + 1,
                }
            ).eq("id", oid).execute()
            if message_id:
                message_update: dict[str, Any] = {"delivered_at": now}
                external_id = max_message_id_from_response(result)
                if external_id:
                    message_update["external_message_id"] = external_id
                client.table("case_messages").update(message_update).eq(
                    "id", str(message_id)
                ).execute()
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("case_chat outbox send failed id=%s: %s", oid[:8], exc)
            attempts = int(row.get("attempts") or 0) + 1
            client.table("case_chat_outbox").update(
                {
                    "status": "failed" if attempts >= MAX_DELIVERY_ATTEMPTS else "pending",
                    "attempts": attempts,
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


def mirror_staff_message_to_max(
    case: dict[str, Any],
    body: str,
    *,
    message_id: str | None = None,
) -> None:
    """Доставить видимое клиенту сообщение специалиста в тот же чат MAX."""
    mirror_client_message_to_max(case, body, message_id=message_id)


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
    if is_client_chat_active(case_id):
        logger.info("chat notify skipped: client active in unified chat case=%s", case_id[:8])
        return
    try:
        from sfrfr.integrations.max.client import MaxBotClient

        bot = MaxBotClient()
        if not bot.available:
            return
        bot.send_message(text=CHAT_NOTIFY_NEUTRAL, user_id=mid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat notify MAX failed case=%s: %s", case_id[:8], exc)


def max_message_id_from_response(payload: Any) -> str | None:
    """Извлечь внешний id сообщения из ответа MAX без привязки к версии API."""
    pending: list[Any] = [payload]
    seen: set[int] = set()
    preferred_keys = ("message_id", "mid")
    fallback_keys = ("id",)
    while pending:
        current = pending.pop(0)
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        for key in preferred_keys:
            value = current.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        for key in ("message", "result", "data"):
            nested = current.get(key)
            if isinstance(nested, dict):
                pending.append(nested)
            elif isinstance(nested, list):
                pending.extend(nested)
        for key in fallback_keys:
            value = current.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def mark_chat_activity(case_id: str, channel: str) -> None:
    """Записать активность клиента в одном из интерфейсов чата."""
    cid = str(case_id or "").strip()
    origin = str(channel or "").strip().lower()
    if not cid or origin not in {"cabinet", "max"}:
        return
    try:
        from sfrfr.db.session import get_supabase_client

        get_supabase_client().table("case_chat_presence").upsert(
            {
                "case_id": cid,
                "channel": origin,
                "last_active_at": datetime.now(UTC).isoformat(),
            },
            on_conflict="case_id,channel",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("chat activity write skipped case=%s channel=%s: %s", cid[:8], origin, exc)


def is_client_chat_active(
    case_id: str,
    *,
    now: datetime | None = None,
    ttl_seconds: int = CHAT_ACTIVITY_TTL_SECONDS,
) -> bool:
    """Проверить недавнюю активность клиента в кабинете или MAX."""
    cid = str(case_id or "").strip()
    if not cid:
        return False
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("case_chat_presence")
            .select("channel,last_active_at")
            .eq("case_id", cid)
            .in_("channel", ["cabinet", "max"])
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("chat activity lookup skipped case=%s: %s", cid[:8], exc)
        return False
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(seconds=max(1, ttl_seconds))
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("last_active_at") or "").replace("Z", "+00:00")
        try:
            active_at = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if active_at.tzinfo is None:
            active_at = active_at.replace(tzinfo=UTC)
        if active_at >= cutoff:
            return True
    return False


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


def find_message_by_client_message_id(
    case_id: str,
    client_message_id: str,
) -> dict[str, Any] | None:
    cid = (case_id or "").strip()
    mid = (client_message_id or "").strip()
    if not cid or not mid:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("*")
            .eq("case_id", cid)
            .eq("client_message_id", mid)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.info("client_message_id lookup skipped case=%s: %s", cid[:8], exc)
        return None


def find_bot_reply_to_message_id(reply_to_message_id: str) -> dict[str, Any] | None:
    target = (reply_to_message_id or "").strip()
    if not target:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("*")
            .eq("reply_to_message_id", target)
            .eq("author_kind", "system")
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.info("reply_to_message_id lookup skipped: %s", exc)
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
