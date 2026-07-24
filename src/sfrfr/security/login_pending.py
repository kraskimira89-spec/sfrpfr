"""Ожидающие входы веб-кабинета через MAX (ПК ждёт подтверждения с телефона)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

Audience = Literal["client", "staff"]
Status = Literal[
    "pending_pair",
    "pending_confirm",
    "pending_manager",
    "approved",
    "expired",
    "cancelled",
]

_TTL_SECONDS = 10 * 60
_lock = threading.Lock()


@dataclass
class PendingLogin:
    ticket_id: str
    pair_code: str
    status: Status
    expires_at: float
    audience: Audience = "client"
    staff_email: str | None = None
    max_user_id: str | None = None
    contact: str | None = None
    token_hash: str | None = None
    email: str | None = None
    manager_notified: bool = False
    created_at: float = field(default_factory=lambda: time.time())


_BY_TICKET: dict[str, PendingLogin] = {}
_BY_CODE: dict[str, str] = {}
_BY_MAX: dict[str, str] = {}


def _purge_locked(now: float | None = None) -> None:
    now = now if now is not None else time.time()
    dead = [tid for tid, p in _BY_TICKET.items() if p.expires_at < now or p.status == "cancelled"]
    for tid in dead:
        p = _BY_TICKET.pop(tid, None)
        if not p:
            continue
        _BY_CODE.pop(p.pair_code, None)
        if p.max_user_id and _BY_MAX.get(p.max_user_id) == tid:
            _BY_MAX.pop(p.max_user_id, None)


def create_pending(
    *,
    audience: Audience = "client",
    staff_email: str | None = None,
    ttl_seconds: int = _TTL_SECONDS,
) -> PendingLogin:
    """Создать сессию входа: сначала код на экране ПК, потом подтверждение в MAX."""
    email = (staff_email or "").strip().lower() or None
    if audience == "staff" and not email:
        raise ValueError("staff_email required for staff audience")
    with _lock:
        _purge_locked()
        ticket_id = secrets.token_urlsafe(18)
        # 6 цифр, без ведущих нулей-ловушек — всегда 6 символов
        pair_code = f"{secrets.randbelow(1_000_000):06d}"
        # коллизии кода крайне редки; перегенерируем
        while pair_code in _BY_CODE:
            pair_code = f"{secrets.randbelow(1_000_000):06d}"
        pending = PendingLogin(
            ticket_id=ticket_id,
            pair_code=pair_code,
            status="pending_pair",
            expires_at=time.time() + ttl_seconds,
            audience=audience,
            staff_email=email,
        )
        _BY_TICKET[ticket_id] = pending
        _BY_CODE[pair_code] = ticket_id
        return pending


def get_pending(ticket_id: str) -> PendingLogin | None:
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p:
            return None
        if p.expires_at < time.time():
            p.status = "expired"
        return p


def bind_max_by_code(*, pair_code: str, max_user_id: str, contact: str) -> PendingLogin | None:
    """Телефон: пользователь ввёл код с экрана ПК в чат MAX."""
    code = "".join(ch for ch in (pair_code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    with _lock:
        _purge_locked()
        tid = _BY_CODE.get(code)
        if not tid:
            return None
        p = _BY_TICKET.get(tid)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        if p.status not in {"pending_pair", "pending_confirm"}:
            return None
        p.max_user_id = str(max_user_id)
        p.contact = contact.strip().lower()
        p.status = "pending_confirm"
        _BY_MAX[str(max_user_id)] = tid
        return p


def bind_max_direct(
    *,
    ticket_id: str,
    max_user_id: str,
    contact: str,
) -> PendingLogin | None:
    """ПК уже знает max_user_id (номер из дела) — сразу ждём кнопку в MAX."""
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        p.max_user_id = str(max_user_id)
        p.contact = contact.strip().lower()
        p.status = "pending_confirm"
        _BY_MAX[str(max_user_id)] = ticket_id
        return p


def latest_for_max(max_user_id: str) -> PendingLogin | None:
    with _lock:
        _purge_locked()
        tid = _BY_MAX.get(str(max_user_id))
        if not tid:
            return None
        p = _BY_TICKET.get(tid)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        return p


def mark_pending_manager(*, ticket_id: str) -> PendingLogin | None:
    """Сотрудник подтвердил в MAX — ждём руководителя."""
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        if p.audience != "staff" or p.status != "pending_confirm":
            return None
        p.status = "pending_manager"
        return p


def mark_manager_notified(*, ticket_id: str) -> None:
    with _lock:
        p = _BY_TICKET.get(ticket_id)
        if p:
            p.manager_notified = True


def approve(*, ticket_id: str, token_hash: str, email: str) -> PendingLogin | None:
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        allowed = {"pending_confirm"} if p.audience == "client" else {"pending_manager", "pending_confirm"}
        if p.status not in allowed:
            return None
        p.status = "approved"
        p.token_hash = token_hash
        p.email = email.strip().lower()
        return p


def approve_for_max(*, max_user_id: str, token_hash: str, email: str) -> PendingLogin | None:
    p = latest_for_max(max_user_id)
    if not p:
        return None
    return approve(ticket_id=p.ticket_id, token_hash=token_hash, email=email)


def callback_payload_for(ticket_id: str) -> str:
    return f"confirm_web_login|{ticket_id}"


def manager_callback_payload_for(ticket_id: str) -> str:
    return f"approve_staff_login|{ticket_id}"


def parse_confirm_callback(payload: str) -> str | None:
    """Вернуть ticket_id из callback или None (общий confirm без id)."""
    raw = (payload or "").strip()
    if raw == "confirm_web_login":
        return ""
    if raw.startswith("confirm_web_login|"):
        return raw.split("|", 1)[1].strip() or None
    return None


def parse_manager_callback(payload: str) -> str | None:
    """ticket_id из callback руководителя или None."""
    raw = (payload or "").strip()
    if raw.startswith("approve_staff_login|"):
        return raw.split("|", 1)[1].strip() or None
    return None
