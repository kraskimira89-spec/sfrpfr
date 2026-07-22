"""Обработка апдейтов MAX → кейс SFRFR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sfrfr.core.case_store import get_case_store
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.models.case_status import CaseStatus
from sfrfr.storage.local import save_upload


@dataclass
class MaxHandleResult:
    ok: bool
    action: str
    case_id: str | None = None
    reply: str | None = None
    detail: str = ""


def _user_id(update: dict[str, Any]) -> str | None:
    for key in ("user_id", "sender_id", "from_id"):
        if key in update and update[key] is not None:
            return str(update[key])
    message = update.get("message") or update.get("message_created") or {}
    if isinstance(message, dict):
        sender = message.get("sender") or message.get("from") or {}
        if isinstance(sender, dict) and sender.get("user_id") is not None:
            return str(sender["user_id"])
        if message.get("user_id") is not None:
            return str(message["user_id"])
    return None


def _chat_id(update: dict[str, Any]) -> int | str | None:
    if update.get("chat_id") is not None:
        return update["chat_id"]
    message = update.get("message") or {}
    if isinstance(message, dict) and message.get("chat_id") is not None:
        return message["chat_id"]
    recipient = update.get("recipient") or {}
    if isinstance(recipient, dict) and recipient.get("chat_id") is not None:
        return recipient["chat_id"]
    return None


def _text(update: dict[str, Any]) -> str:
    message = update.get("message") or update.get("message_created") or update
    if not isinstance(message, dict):
        return ""
    body = message.get("body") or message.get("text") or ""
    if isinstance(body, dict):
        return str(body.get("text") or "")
    return str(body or "")


def _reply(bot: MaxBotClient, chat_id: int | str | None, text: str) -> None:
    if chat_id is not None:
        bot.send_message(chat_id=chat_id, text=text)


def handle_max_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    Сценарий MVP:
    /start — создать/продолжить кейс
    /status, /run, /help
    file_name + file_bytes — сохранить вложение (тесты / будущий download)
    """
    bot = bot or MaxBotClient()
    text = _text(update).strip()
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    lower = text.lower()

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    store = get_case_store()

    if lower.startswith("/start") or lower in {"старт", "начать"}:
        existing = store.find_by_max_user(user_id)
        if existing:
            reply = (
                f"Снова здравствуйте. Ваш кейс: {existing.case_id}\n"
                f"Статус: {existing.ctx.status}\n"
                "Пришлите документы (ИЛС и трудовую) или команду /status."
            )
            _reply(bot, chat_id, reply)
            return MaxHandleResult(ok=True, action="resume", case_id=existing.case_id, reply=reply)

        record = store.create(
            client_name=f"MAX user {user_id}",
            snils_masked="***-***-*** **",
            consent_given=True,
        )
        store.bind_max(
            record.case_id,
            max_user_id=user_id,
            max_chat_id=str(chat_id) if chat_id is not None else None,
        )
        reply = (
            "Здравствуйте! Я помогу с аудитом пенсионного дела.\n"
            f"Создан кейс: {record.case_id}\n"
            "Пришлите сканы/PDF: выписку ИЛС и трудовую книжку.\n"
            "Команды: /status, /run, /help"
        )
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="create", case_id=record.case_id, reply=reply)

    record = store.find_by_max_user(user_id)
    if record is None:
        reply = "Напишите /start, чтобы создать кейс."
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="need_start", reply=reply)

    if lower.startswith("/help"):
        reply = "Команды: /start, /status, /run. Документы — файлом в чат."
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="help", case_id=record.case_id, reply=reply)

    if lower.startswith("/status"):
        reply = (
            f"Кейс {record.case_id}\n"
            f"Статус: {record.ctx.status}\n"
            f"Документов: {len(record.ctx.document_paths)}\n"
            f"OCR: {len(record.ctx.ocr_texts)}\n"
            f"Findings: {len(record.ctx.findings)}"
        )
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="status", case_id=record.case_id, reply=reply)

    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = "Сначала пришлите документы (ИЛС и трудовую)."
            _reply(bot, chat_id, reply)
            return MaxHandleResult(ok=False, action="run_blocked", case_id=record.case_id, reply=reply)
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = " Черновик готов к проверке юристом." if updated.ctx.draft else ""
        reply = (
            f"Пайплайн: {updated.ctx.status}. Findings: {len(updated.ctx.findings)}."
            f"{draft_note}"
        )
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        path = save_upload(record.case_id, file_name, bytes(file_bytes))
        fresh = store.add_document(record.case_id, str(path))
        reply = (
            f"Файл «{file_name}» принят. Документов: {len(fresh.ctx.document_paths)}. "
            "Когда будете готовы — /run"
        )
        _reply(bot, chat_id, reply)
        return MaxHandleResult(ok=True, action="upload", case_id=record.case_id, reply=reply)

    reply = (
        "Принял сообщение. Пришлите файл документа или команды /status /run.\n"
        f"Текущий статус: {record.ctx.status}"
    )
    _reply(bot, chat_id, reply)
    return MaxHandleResult(ok=True, action="ack", case_id=record.case_id, reply=reply)
