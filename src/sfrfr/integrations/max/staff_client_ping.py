"""Короткий пинг специалистам: новое сообщение клиента в чате MAX."""

from __future__ import annotations

_SEEN: dict[str, str] = {}


def reset_staff_ping_cache() -> None:
    _SEEN.clear()


def ping_fingerprint(text: str) -> str:
    return " ".join((text or "").split())[:500]


def should_send_ping(
    *,
    key: str,
    fingerprint: str,
    seen: dict[str, str] | None = None,
) -> bool:
    """False, если тот же фрагмент уже уходил по этому ключу."""
    store = _SEEN if seen is None else seen
    if store.get(key) == fingerprint:
        return False
    store[key] = fingerprint
    return True


def build_client_ping(*, who: str, snippet: str, staff_url: str | None) -> str:
    frag = " ".join((snippet or "").split())[:140]
    lines = [f"Сообщение: {who}", f"«{frag}»"]
    if staff_url:
        lines.append(staff_url)
    return "\n".join(lines)


def notify_staff_client_message(
    *,
    user_id: str,
    case_id: str | None,
    snippet: str,
    kind: str = "text",
) -> bool:
    """DM + канал специалистов. Повтор того же текста не шлём."""
    cid = (case_id or "").strip()
    body = (snippet or "").strip()
    if not cid or not body:
        return False
    key = f"{kind}:{user_id}:{cid}"
    if not should_send_ping(key=key, fingerprint=ping_fingerprint(body)):
        return False
    from sfrfr.integrations.amocrm.urls import admin_case_max_reply_url
    from sfrfr.integrations.max.handler import _fanout_ops_text

    url = admin_case_max_reply_url(cid)
    text = build_client_ping(who=f"MAX {user_id}", snippet=body, staff_url=url)
    _fanout_ops_text(text)
    return True
