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
)
from sfrfr.models.case_status import CaseStatus, status_label_ru
from sfrfr.security.login_otp import (
    CONFIRM_WEB_LOGIN_CALLBACK,
    CONFIRM_WEB_LOGIN_LABEL,
    confirm_web_login_message,
)
from sfrfr.security.login_pending import (
    approve,
    bind_max_by_code,
    callback_payload_for,
    get_pending,
    latest_for_max,
    mark_manager_notified,
    mark_pending_manager,
    manager_callback_payload_for,
    parse_confirm_callback,
    parse_manager_callback,
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
    # Без ticket — подтвердит последнюю сессию с ПК для этого max_user_id
    return inline_callback_keyboard(CONFIRM_WEB_LOGIN_LABEL, CONFIRM_WEB_LOGIN_CALLBACK)


def _channel_choice_text() -> str:
    settings = get_settings()
    cabinet = settings.cabinet_public_url.rstrip("/")
    return (
        "\n\n"
        "Как войти в кабинет на компьютере:\n"
        f"1) Откройте {cabinet}/\n"
        "2) Нажмите «Подтвердить вход через MAX».\n"
        "3) Пришлите сюда код с экрана компьютера.\n"
        "4) Нажмите «Подтвердить вход в веб кабинет» — кабинет откроется на ПК."
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


def _token_hash_for_email(email: str) -> str | None:
    """hashed_token magic link для указанного email (без создания клиента)."""
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.db.staff_roles import find_user_by_email

        normalized = email.strip().lower()
        if "@" not in normalized:
            return None
        client = get_supabase_client()
        if find_user_by_email(normalized) is None:
            client.auth.admin.create_user(
                {
                    "email": normalized,
                    "email_confirm": True,
                    "app_metadata": {"role_source": "staff_max_login"},
                }
            )
        link = client.auth.admin.generate_link({"type": "magiclink", "email": normalized})
        props = getattr(link, "properties", None)
        if props is None and isinstance(link, dict):
            props = link.get("properties") or link
        hashed = None
        if props is not None:
            hashed = getattr(props, "hashed_token", None) or (
                props.get("hashed_token") if isinstance(props, dict) else None
            )
        return str(hashed) if hashed else None
    except Exception:
        return None


def _token_hash_for_max(max_user_id: str) -> tuple[str, str] | None:
    """(email, token_hash) для Supabase session на ПК."""
    try:
        from sfrfr.db.session import get_supabase_client
        from sfrfr.db.staff_roles import find_user_by_email

        _ensure_supabase_max_client(max_user_id)
        row = _client_row_by_max(max_user_id)
        if not row:
            return None
        email = _auth_email_for_row(row, max_user_id)
        client = get_supabase_client()
        existing = find_user_by_email(email)
        if existing is None:
            client.auth.admin.create_user(
                {
                    "email": email,
                    "email_confirm": True,
                    "app_metadata": {"role_source": "max_otp_login"},
                }
            )
        hashed = _token_hash_for_email(email)
        if not hashed:
            return None
        return email, hashed
    except Exception:
        return None


def _notify_managers_staff_login(
    bot: MaxBotClient,
    *,
    pending,
) -> int:
    """Отправить руководителям кнопку одобрения. Вернуть число успешных отправок."""
    from sfrfr.db.staff_roles import list_manager_max_user_ids
    from sfrfr.security.login_otp import APPROVE_STAFF_LOGIN_LABEL

    settings = get_settings()
    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    chat_ids = [
        p.strip()
        for p in (settings.staff_login_approver_max_chat_ids or "").split(",")
        if p.strip()
    ]
    if not manager_ids and not chat_ids:
        return 0
    email = pending.staff_email or pending.contact or "сотрудник"
    text = (
        f"Сотрудник {email} запросил вход в кабинет сотрудника.\n"
        "Если это ожидаемый вход — нажмите кнопку ниже."
    )
    attachments = inline_callback_keyboard(
        APPROVE_STAFF_LOGIN_LABEL,
        manager_callback_payload_for(pending.ticket_id),
    )
    sent = 0
    targets = manager_ids or [None] * max(1, len(chat_ids))
    for i, mid in enumerate(targets):
        cid = chat_ids[i] if i < len(chat_ids) else None
        try:
            bot.send_message(
                text=text,
                user_id=str(mid) if mid else None,
                chat_id=cid,
                attachments=attachments,
            )
            sent += 1
        except Exception:
            # fallback: только chat_id
            if cid and mid:
                try:
                    bot.send_message(text=text, chat_id=cid, attachments=attachments)
                    sent += 1
                except Exception:
                    continue
            continue
    if sent:
        mark_manager_notified(ticket_id=pending.ticket_id)
    return sent


def _complete_pc_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str | None,
) -> MaxHandleResult:
    """Подтверждение с телефона → сессия для poll на ПК (клиент) или ожидание руководителя (staff)."""
    pending = None
    if ticket_id:
        pending = get_pending(ticket_id)
    if pending is None:
        pending = latest_for_max(user_id)
    if pending is None or pending.status not in {"pending_confirm", "pending_pair"}:
        reply = (
            "Сначала на компьютере откройте кабинет и нажмите "
            "«Подтвердить вход через MAX», затем пришлите код сюда."
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_no_pending", reply=reply)

    if pending.status == "pending_pair" or not pending.max_user_id:
        # ещё не ввели код — привяжем текущего пользователя и попросим подтвердить ещё раз
        _ensure_supabase_max_client(user_id)
        row = _client_row_by_max(user_id)
        if not row:
            reply = "Сначала /start, затем код с компьютера."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_need_start", reply=reply)
        contact = _auth_email_for_row(row, user_id)
        pending = bind_max_by_code(
            pair_code=pending.pair_code,
            max_user_id=user_id,
            contact=contact,
        ) or pending
        if pending.status != "pending_confirm":
            _send_confirm_button(bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id)
            reply = "Нажмите кнопку подтверждения ещё раз."
            return MaxHandleResult(ok=True, action="login_need_confirm", reply=reply)

    # Staff: после подтверждения сотрудником — этап руководителя
    if pending.audience == "staff":
        from sfrfr.db.staff_roles import get_staff_role_by_email

        staff_email = (pending.staff_email or "").strip().lower()
        if not staff_email or get_staff_role_by_email(staff_email) is None:
            reply = "Этот email не в staff-ролях. Вход отклонён."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_not_staff", reply=reply)
        waiting = mark_pending_manager(ticket_id=pending.ticket_id)
        if not waiting:
            reply = "Сессия устарела. На компьютере начните вход через MAX снова."
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=False, action="login_expired", reply=reply)
        sent = _notify_managers_staff_login(bot, pending=waiting)
        if sent == 0:
            reply = (
                "Вы подтвердили вход. Руководители не настроены в системе "
                "(нужен max_user_id у admin или STAFF_LOGIN_APPROVER_MAX_USER_IDS). "
                "Обратитесь к администратору."
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
            return MaxHandleResult(ok=True, action="login_pending_manager_no_approvers", reply=reply)
        reply = (
            "Вы подтвердили вход.\n"
            "Ожидайте подтверждения руководителя в MAX — кабинет откроется на компьютере."
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=True, action="login_pending_manager", reply=reply)

    tokens = _token_hash_for_max(user_id)
    if not tokens:
        reply = "Не удалось завершить вход. Попробуйте ещё раз через минуту."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_token_failed", reply=reply)
    email, token_hash = tokens
    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=email)
    if not approved:
        reply = "Сессия устарела. На компьютере нажмите вход через MAX снова."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="login_expired", reply=reply)

    reply = (
        "Вход подтверждён.\n"
        "Кабинет должен открыться на компьютере в течение нескольких секунд.\n"
        "Если не открылся — обновите страницу кабинета."
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    return MaxHandleResult(ok=True, action="login_approved", reply=reply)


def _approve_staff_by_manager(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str,
) -> MaxHandleResult:
    """Руководитель разрешил вход сотрудника на ПК."""
    from sfrfr.db.staff_roles import get_staff_role_by_email, list_manager_max_user_ids

    settings = get_settings()
    manager_ids = list_manager_max_user_ids(
        extra_ids=settings.staff_login_approver_max_user_ids,
    )
    if str(user_id) not in {str(m) for m in manager_ids}:
        reply = "У вас нет права подтверждать вход сотрудников."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_forbidden", reply=reply)

    pending = get_pending(ticket_id)
    if pending is None or pending.status != "pending_manager":
        reply = "Заявка на вход не найдена или уже обработана."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_no_pending", reply=reply)

    staff_email = (pending.staff_email or "").strip().lower()
    if not staff_email or get_staff_role_by_email(staff_email) is None:
        reply = "Email сотрудника не в staff-ролях."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_not_staff", reply=reply)

    token_hash = _token_hash_for_email(staff_email)
    if not token_hash:
        reply = "Не удалось выдать сессию. Попробуйте позже."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_token_failed", reply=reply)

    approved = approve(ticket_id=pending.ticket_id, token_hash=token_hash, email=staff_email)
    if not approved:
        reply = "Не удалось подтвердить (сессия устарела)."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="manager_expired", reply=reply)

    reply = (
        f"Вход для {staff_email} разрешён.\n"
        "Кабинет сотрудника откроется на компьютере сотрудника."
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
    # уведомить сотрудника в MAX, если известен
    if pending.max_user_id and str(pending.max_user_id) != str(user_id):
        try:
            bot.send_message(
                text="Руководитель разрешил вход. Кабинет должен открыться на компьютере.",
                user_id=str(pending.max_user_id),
            )
        except Exception:
            pass
    return MaxHandleResult(ok=True, action="manager_approved", reply=reply)


def _send_confirm_button(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    ticket_id: str,
) -> None:
    text = confirm_web_login_message()
    attachments = inline_callback_keyboard(
        CONFIRM_WEB_LOGIN_LABEL,
        callback_payload_for(ticket_id),
    )
    _reply(bot, user_id=user_id, chat_id=chat_id, text=text, attachments=attachments)


def _handle_pair_code(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    code: str,
) -> MaxHandleResult:
    _ensure_supabase_max_client(user_id)
    row = _client_row_by_max(user_id)
    if not row:
        reply = "Сначала напишите /start, затем снова отправьте код с компьютера."
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="pair_need_start", reply=reply)
    contact = _auth_email_for_row(row, user_id)
    pending = bind_max_by_code(pair_code=code, max_user_id=user_id, contact=contact)
    if not pending:
        reply = (
            "Код не найден или устарел. На компьютере снова нажмите "
            "«Подтвердить вход через MAX» и пришлите новый код."
        )
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
        return MaxHandleResult(ok=False, action="pair_invalid", reply=reply)
    _send_confirm_button(bot, user_id=user_id, chat_id=chat_id, ticket_id=pending.ticket_id)
    if pending.audience == "staff":
        reply = (
            "Код принят. Нажмите кнопку ниже — затем вход подтвердит руководитель."
        )
    else:
        reply = "Код принят. Нажмите кнопку ниже — кабинет откроется на компьютере."
    return MaxHandleResult(ok=True, action="pair_ok", reply=reply)


def _send_confirm_web_login(
    bot: MaxBotClient,
    *,
    user_id: str,
    chat_id: int | str | None,
    callback_payload: str = "",
) -> MaxHandleResult:
    """Кнопка/команда подтверждения: завершает вход на ПК, не открывает ссылку на телефоне."""
    ticket_from_cb = parse_confirm_callback(callback_payload)
    if ticket_from_cb is None and callback_payload:
        # не наш callback
        ticket_from_cb = None
    ticket_id = ticket_from_cb if ticket_from_cb else None
    if ticket_from_cb == "":
        ticket_id = None
    return _complete_pc_login(bot, user_id=user_id, chat_id=chat_id, ticket_id=ticket_id)


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
    confirm_cb = parse_confirm_callback(callback)
    manager_ticket = parse_manager_callback(callback)
    login_hit = (
        confirm_cb is not None
        or lower in _LOGIN_TRIGGERS
        or lower.startswith("/login")
        or CONFIRM_WEB_LOGIN_LABEL.lower() in lower
    )

    if not user_id:
        return MaxHandleResult(ok=False, action="ignore", detail="no user_id")

    store = get_case_store()

    if manager_ticket:
        return _approve_staff_by_manager(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            ticket_id=manager_ticket,
        )

    if login_hit:
        return _send_confirm_web_login(
            bot,
            user_id=user_id,
            chat_id=chat_id,
            callback_payload=callback,
        )

    # Код с экрана компьютера (6 цифр)
    digits_only = "".join(ch for ch in text if ch.isdigit())
    if len(digits_only) == 6 and len(text.replace(" ", "")) <= 8:
        return _handle_pair_code(bot, user_id=user_id, chat_id=chat_id, code=digits_only)

    if lower.startswith("/start") or lower in {"старт", "начать"}:
        _ensure_supabase_max_client(user_id)
        existing = store.find_by_max_user(user_id)
        if existing:
            reply = (
                f"Снова здравствуйте. Ваш кейс: {existing.case_id}\n"
                f"Этап: {status_label_ru(existing.ctx.status)}\n"
                + _docs_request_text(has_docs=bool(existing.ctx.document_paths))
                + _channel_choice_text()
            )
            _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
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
        _reply(bot, user_id=user_id, chat_id=chat_id, text=reply)
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
