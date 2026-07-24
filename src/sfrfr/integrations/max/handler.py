"""Обработка апдейтов MAX → кейс SFRFR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sfrfr.core.case_store import get_case_store
from sfrfr.core.config import get_settings
from sfrfr.integrations.max.attachments import download_file, extract_downloadable_files
from sfrfr.integrations.max.client import (
    MaxBotClient,
    inline_callback_keyboard,
    inline_link_keyboard,
)
from sfrfr.models.case_status import CaseStatus, status_label_ru
from sfrfr.security.login_otp import (
    CONFIRM_WEB_LOGIN_CALLBACK,
    CONFIRM_WEB_LOGIN_LABEL,
    confirm_web_login_message,
    issue_login_link,
)
from sfrfr.storage.local import save_upload


@dataclass
class MaxHandleResult:
    ok: bool
    action: str
    case_id: str | None = None
    reply: str | None = None
    detail: str = ""


_DEFAULT_DOC_REQUESTS = (
    "Выписка ИЛС (лицевой счёт)",
    "Трудовая книжка / сведения о стаже",
    "Решение СФР (если уже есть)",
)

_LOGIN_TRIGGERS = frozenset(
    {
        "/login",
        "войти",
        "вход",
        CONFIRM_WEB_LOGIN_LABEL.lower(),
        CONFIRM_WEB_LOGIN_CALLBACK,
        "confirm_web_login",
    }
)


def _user_id(update: dict[str, Any]) -> str | None:
    for key in ("user_id", "sender_id", "from_id"):
        if key in update and update[key] is not None:
            return str(update[key])
    callback = update.get("callback") or {}
    if isinstance(callback, dict):
        user = callback.get("user") or callback.get("from") or {}
        if isinstance(user, dict) and user.get("user_id") is not None:
            return str(user["user_id"])
        if callback.get("user_id") is not None:
            return str(callback["user_id"])
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
    callback = update.get("callback") or {}
    if isinstance(callback, dict):
        if callback.get("chat_id") is not None:
            return callback["chat_id"]
        msg = callback.get("message") or {}
        if isinstance(msg, dict) and msg.get("chat_id") is not None:
            return msg["chat_id"]
    message = update.get("message") or {}
    if isinstance(message, dict):
        if message.get("chat_id") is not None:
            return message["chat_id"]
        recipient = message.get("recipient") or {}
        if isinstance(recipient, dict) and recipient.get("chat_id") is not None:
            return recipient["chat_id"]
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


def _callback_payload(update: dict[str, Any]) -> str:
    """payload/data из message_callback."""
    update_type = str(update.get("update_type") or update.get("type") or "")
    for key in ("callback", "message_callback"):
        block = update.get(key)
        if isinstance(block, dict):
            raw = block.get("payload") or block.get("data") or block.get("callback_data")
            if raw is not None:
                return str(raw).strip()
    if "callback" in update_type or update.get("callback_id") is not None:
        raw = update.get("payload") or update.get("data") or update.get("callback_data")
        if raw is not None:
            return str(raw).strip()
    return ""


def _reply(
    bot: MaxBotClient,
    *,
    user_id: str | None,
    chat_id: int | str | None,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    try:
        bot.send_message(
            text=text,
            user_id=user_id,
            chat_id=chat_id,
            attachments=attachments,
        )
    except Exception:
        pass


def _login_menu_keyboard() -> list[dict[str, Any]]:
    return inline_callback_keyboard(CONFIRM_WEB_LOGIN_LABEL, CONFIRM_WEB_LOGIN_CALLBACK)


def _channel_choice_text() -> str:
    settings = get_settings()
    cabinet = settings.cabinet_public_url.rstrip("/")
    miniapp = settings.max_miniapp_url.rstrip("/") + "/"
    return (
        "\n\n"
        f"1) {CONFIRM_WEB_LOGIN_LABEL} — кнопка ниже.\n"
        f"2) Документы можно прислать сюда файлом или загрузить в кабинете: {cabinet}/\n"
        f"3) Мини-приложение MAX (по желанию): {miniapp}"
    )


def _ensure_supabase_max_client(max_user_id: str) -> None:
    """Неблокирующая регистрация клиента MAX в Supabase (единый профиль ТЗ-09)."""
    try:
        from sfrfr.db.client_channels import ClientChannelRepository

        ClientChannelRepository().ensure_for_max_user(max_user_id)
    except Exception:
        pass


def _client_row_by_max(max_user_id: str) -> dict[str, Any] | None:
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("clients")
            .select("*")
            .eq("max_user_id", str(max_user_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _auth_email_for_row(row: dict[str, Any], max_user_id: str) -> str:
    email = (row.get("email") or "").strip().lower()
    if email and "@" in email:
        return email
    return f"max_{max_user_id}@clients.sfrfr.local"


def _send_confirm_web_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
) -> MaxHandleResult:
    """Выдать ссылку и код: «Подтвердить вход в веб кабинет»."""
    _ensure_supabase_max_client(user_id)
    row = _client_row_by_max(user_id)
    if not row:
        reply = (
            f"Сначала напишите /start, затем нажмите «{CONFIRM_WEB_LOGIN_LABEL}»."
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_need_start", reply=reply)

    contact = _auth_email_for_row(row, user_id)
    try:
        issued = issue_login_link(contact=contact, max_user_id=str(user_id))
    except Exception as exc:  # noqa: BLE001
        reply = "Не удалось подготовить вход. Попробуйте ещё раз через минуту."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_issue_failed", reply=reply, detail=str(exc))

    text = confirm_web_login_message(code=issued.code)
    attachments = inline_link_keyboard(CONFIRM_WEB_LOGIN_LABEL, issued.login_url)
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        attachments=attachments,
    )
    try:
        from sfrfr.db.client_channels import ClientChannelRepository

        ClientChannelRepository().audit(
            str(row.get("user_id") or row.get("id")),
            f"login_link_max_sent:{user_id}",
        )
    except Exception:
        pass
    return MaxHandleResult(ok=True, action="login_link_sent", reply=text)


def _docs_request_text(*, has_docs: bool) -> str:
    lines = ["Нужны документы для проверки:"]
    for i, title in enumerate(_DEFAULT_DOC_REQUESTS, start=1):
        lines.append(f"{i}. {title}")
    lines.append("Пришлите файлы в этот чат (PDF/JPG/PNG) или загрузите в кабинете.")
    if has_docs:
        lines.append("Часть файлов уже получена — можно /status или /run.")
    return "\n".join(lines)


def _draft_preview(record) -> str:  # noqa: ANN001 - CaseRecord
    draft = record.ctx.draft
    if not draft:
        return (
            "Черновик ещё не готов. Пришлите документы и выполните /run "
            "(до этапа проверки специалистом)."
        )
    body = (draft.body or "").strip()
    preview = body[:1500] + ("…" if len(body) > 1500 else "")
    title = draft.title or "Черновик заявления"
    note = "\n\n⚠️ Это черновик для проверки специалистом, не подача в СФР."
    return f"{title}\n\n{preview}{note}"


def _ingest_bytes(store, record, file_name: str, data: bytes):  # noqa: ANN001
    path = save_upload(record.case_id, file_name, data)
    return store.add_document(record.case_id, str(path))


def handle_max_update(
    update: dict[str, Any],
    *,
    bot: MaxBotClient | None = None,
) -> MaxHandleResult:
    """
    Сценарий MVP:
    /start — создать/продолжить кейс + кнопка входа в веб-кабинет
    «Подтвердить вход в веб кабинет» — одноразовая ссылка
    /status, /run, /draft, /docs, /help
    вложения — скачать по url или file_bytes
    """
    bot = bot or MaxBotClient()
    text = _text(update).strip()
    callback = _callback_payload(update)
    user_id = _user_id(update)
    chat_id = _chat_id(update)
    lower = text.lower()
    login_hit = (
        callback == CONFIRM_WEB_LOGIN_CALLBACK
        or lower in _LOGIN_TRIGGERS
        or lower.startswith("/login")
        or CONFIRM_WEB_LOGIN_LABEL.lower() in lower
    )

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    store = get_case_store()

    if login_hit:
        return _send_confirm_web_login(bot, user_id=user_id, chat_id=chat_id)

    if lower.startswith("/start") or lower in {"старт", "начать"}:
        _ensure_supabase_max_client(user_id)
        existing = store.find_by_max_user(user_id)
        menu = _login_menu_keyboard()
        if existing:
            reply = (
                f"Снова здравствуйте. Ваш кейс: {existing.case_id}\n"
                f"Этап: {status_label_ru(existing.ctx.status)}\n"
                + _docs_request_text(has_docs=bool(existing.ctx.document_paths))
                + _channel_choice_text()
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply, attachments=menu)
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
            + _docs_request_text(has_docs=False)
            + "\nКоманды: /status, /docs, /run, /draft, /help"
            + _channel_choice_text()
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply, attachments=menu)
        return MaxHandleResult(ok=True, action="create", case_id=record.case_id, reply=reply)

    record = store.find_by_max_user(user_id)
    if record is None:
        reply = "Напишите /start, чтобы создать кейс."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="need_start", reply=reply)

    if lower.startswith("/help") or lower in {"канал", "/cabinet", "/web"}:
        reply = (
            "Команды: /start, /status, /docs, /run, /draft, /help, /login."
            " Документы — файлом в чат."
            + _channel_choice_text()
        )
        _reply(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            text=reply,
            attachments=_login_menu_keyboard(),
        )
        return MaxHandleResult(ok=True, action="help", case_id=record.case_id, reply=reply)

    if lower.startswith("/docs") or lower in {"документы", "что прислать"}:
        reply = _docs_request_text(has_docs=bool(record.ctx.document_paths))
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="docs_request", case_id=record.case_id, reply=reply)

    if lower.startswith("/draft"):
        reply = _draft_preview(record)
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(
            ok=bool(record.ctx.draft),
            action="draft",
            case_id=record.case_id,
            reply=reply,
        )

    if lower.startswith("/status"):
        reply = (
            f"Кейс {record.case_id}\n"
            f"Этап: {status_label_ru(record.ctx.status)}\n"
            f"Документов: {len(record.ctx.document_paths)}\n"
            f"Распознано текстов: {len(record.ctx.ocr_texts)}\n"
            f"Находок: {len(record.ctx.findings)}\n"
            f"Черновик: {'есть — /draft' if record.ctx.draft else 'ещё нет'}"
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="status", case_id=record.case_id, reply=reply)

    if lower.startswith("/run"):
        if not record.ctx.document_paths and not record.ctx.ocr_texts:
            reply = (
                "Сначала пришлите документы.\n"
                + _docs_request_text(has_docs=False)
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=False,
                action="run_blocked",
                case_id=record.case_id,
                reply=reply,
            )
        updated = store.run_until(record.case_id, stop_at=CaseStatus.HUMAN_REVIEW)
        draft_note = (
            " Черновик готов — откройте /draft."
            if updated.ctx.draft
            else ""
        )
        reply = (
            f"Этап: {status_label_ru(updated.ctx.status)}. "
            f"Находок: {len(updated.ctx.findings)}."
            f"{draft_note}"
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="run", case_id=record.case_id, reply=reply)

    file_name = update.get("file_name")
    file_bytes = update.get("file_bytes")
    if isinstance(file_name, str) and isinstance(file_bytes, (bytes, bytearray)):
        fresh = _ingest_bytes(store, record, file_name, bytes(file_bytes))
        reply = (
            f"Файл «{file_name}» принят. Документов: {len(fresh.ctx.document_paths)}. "
            "Когда будете готовы — /run. Список нужных — /docs"
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="upload", case_id=record.case_id, reply=reply)

    downloads = extract_downloadable_files(update)
    if downloads:
        names: list[str] = []
        fresh = record
        for name, url in downloads:
            try:
                data = download_file(url)
                fresh = _ingest_bytes(store, fresh, name, data)
                names.append(name)
            except Exception:
                continue
        if names:
            reply = (
                f"Принято файлов: {len(names)} ({', '.join(names)}). "
                f"Всего документов: {len(fresh.ctx.document_paths)}. "
                "Команда /run запустит проверку."
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(
                ok=True, action="upload_url", case_id=record.case_id, reply=reply
            )

    reply = (
        "Принял сообщение. Пришлите файл или команды:\n"
        f"«{CONFIRM_WEB_LOGIN_LABEL}» или /login — вход в веб-кабинет\n"
        "/docs — что загрузить\n"
        "/status /run /draft /help\n"
        f"Текущий этап: {status_label_ru(record.ctx.status)}"
    )
    _reply(
        bot,
        user_id=user_id,
        chat_id=chat_id,
        text=reply,
        attachments=_login_menu_keyboard(),
    )
    return MaxHandleResult(ok=True, action="ack", case_id=record.case_id, reply=reply)
