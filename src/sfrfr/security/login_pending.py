"""Ожидающие входы веб-кабинета через MAX (код в MAX → ввод на сайте)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

Audience = Literal["client", "staff"]
Status = Literal[
    "pending_pair",
    "code_sent",
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
    otp_verify_ticket: str | None = None
    manager_notified: bool = False
    created_at: float = field(default_factory=lambda: time.time())


_BY_TICKET: dict[str, PendingLogin] = {}
_BY_CODE: dict[str, str] = {}
_BY_MAX: dict[str, str] = {}
# Код из MAX → otp verify_ticket (чтобы на сайте вводить только код)
_BY_OTP_CODE: dict[str, tuple[str, float]] = {}


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
    stale_otp = [c for c, (_t, exp) in _BY_OTP_CODE.items() if exp < now]
    for c in stale_otp:
        _BY_OTP_CODE.pop(c, None)


def create_pending(
    *,
    audience: Audience = "client",
    staff_email: str | None = None,
    ttl_seconds: int = _TTL_SECONDS,
) -> PendingLogin:
    """Создать сессию входа (клиент: ждём код из MAX; staff: pair на экране)."""
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
    """Legacy/staff: пользователь ввёл код с экрана ПК в чат MAX."""
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
        if p.status not in {"pending_pair", "pending_confirm", "code_sent"}:
            return None
        p.max_user_id = str(max_user_id)
        if p.audience == "staff" and p.staff_email:
            p.contact = p.staff_email.strip().lower()
        else:
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
    """Привязать MAX к ожидающему ticket (сайт или бот)."""
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        p.max_user_id = str(max_user_id)
        p.contact = contact.strip().lower()
        if p.status == "pending_pair":
            p.status = "pending_confirm"
        _BY_MAX[str(max_user_id)] = ticket_id
        return p


def attach_otp_verify_ticket(
    *,
    ticket_id: str,
    otp_verify_ticket: str,
    otp_code: str | None = None,
    max_user_id: str | None = None,
    contact: str | None = None,
) -> PendingLogin | None:
    """Код отправлен в MAX — сайт может принять verify_ticket + код."""
    with _lock:
        _purge_locked()
        p = _BY_TICKET.get(ticket_id)
        if not p or p.expires_at < time.time():
            if p:
                p.status = "expired"
            return None
        if max_user_id:
            p.max_user_id = str(max_user_id)
            _BY_MAX[str(max_user_id)] = ticket_id
        if contact:
            p.contact = contact.strip().lower()
        p.otp_verify_ticket = otp_verify_ticket
        p.status = "code_sent"
        code = "".join(ch for ch in (otp_code or "") if ch.isdigit())
        if len(code) == 6:
            _BY_OTP_CODE[code] = (otp_verify_ticket, p.expires_at)
        return p


def lookup_otp_verify_ticket_by_code(otp_code: str) -> str | None:
    """Найти verify_ticket по 6-значному коду из MAX."""
    code = "".join(ch for ch in (otp_code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    with _lock:
        _purge_locked()
        row = _BY_OTP_CODE.get(code)
        if not row:
            return None
        ticket, exp = row
        if exp < time.time():
            _BY_OTP_CODE.pop(code, None)
            return None
        return ticket


def consume_otp_code(otp_code: str) -> None:
    code = "".join(ch for ch in (otp_code or "") if ch.isdigit())
    with _lock:
        _BY_OTP_CODE.pop(code, None)


def ensure_pending_for_max(
    *,
    max_user_id: str,
    contact: str,
    ttl_seconds: int = _TTL_SECONDS,
) -> PendingLogin:
    """Найти активный pending для MAX, незанятый client pending, или создать новый."""
    mid = str(max_user_id)
    contact_n = contact.strip().lower()
    with _lock:
        _purge_locked()
        tid = _BY_MAX.get(mid)
        if tid:
            p = _BY_TICKET.get(tid)
            if (
                p
                and p.expires_at >= time.time()
                and p.status in {"pending_pair", "pending_confirm", "code_sent"}
                and p.audience == "client"
            ):
                p.contact = contact_n
                p.max_user_id = mid
                return p
        # Сайт уже создал pending без max — забрать самый свежий
        unbound = [
            p
            for p in _BY_TICKET.values()
            if p.audience == "client"
            and p.status == "pending_pair"
            and not p.max_user_id
            and p.expires_at >= time.time()
        ]
        if unbound:
            unbound.sort(key=lambda x: x.created_at, reverse=True)
            p = unbound[0]
            p.max_user_id = mid
            p.contact = contact_n
            p.status = "pending_confirm"
            _BY_MAX[mid] = p.ticket_id
            return p
        ticket_id = secrets.token_urlsafe(18)
        pair_code = f"{secrets.randbelow(1_000_000):06d}"
        while pair_code in _BY_CODE:
            pair_code = f"{secrets.randbelow(1_000_000):06d}"
        pending = PendingLogin(
            ticket_id=ticket_id,
            pair_code=pair_code,
            status="pending_confirm",
            expires_at=time.time() + ttl_seconds,
            audience="client",
            max_user_id=mid,
            contact=contact_n,
        )
        _BY_TICKET[ticket_id] = pending
        _BY_CODE[pair_code] = ticket_id
        _BY_MAX[mid] = ticket_id
        return pending


def latest_unbound_staff_pending() -> PendingLogin | None:
    """Самый свежий staff-вход без привязки к MAX (код ещё на admin)."""
    with _lock:
        _purge_locked()
        candidates = [
            p
            for p in _BY_TICKET.values()
            if p.audience == "staff"
            and p.status == "pending_pair"
            and not p.max_user_id
            and p.expires_at >= time.time()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.created_at, reverse=True)
        return candidates[0]


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
        if p.audience == "client":
            allowed = {"pending_confirm", "code_sent"}
        else:
            allowed = {"pending_manager", "pending_confirm"}
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
