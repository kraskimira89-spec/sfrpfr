"""Входящая почта через IMAP XOAUTH2 (Яндекс Почта, read-only)."""

from __future__ import annotations

import email
import imaplib
import ssl
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from typing import Any, cast

from sfrfr.ai.pii.depersonalize import depersonalize_text
from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.mail import _xoauth2_plain
from sfrfr.integrations.yandex_workspace.oauth import token_available, workspace_email

_IMAP_HOST = "imap.yandex.ru"
_IMAP_PORT = 993
_FORBIDDEN_BODY_MARKERS = ("снилс", "snils", "passport", "паспорт", "ils", "илс")


def _decode_mime(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value.strip()


def _redact_preview(text: str, *, max_len: int = 500) -> str:
    cleaned = depersonalize_text(text or "")
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def _subject_safe(subject: str) -> str:
    subj = _decode_mime(subject)
    low = subj.lower()
    if any(marker in low for marker in _FORBIDDEN_BODY_MARKERS):
        return _redact_preview(subj, max_len=200)
    return subj[:200]


def _imap_fetch_parts(msg_data: list[Any] | None) -> tuple[bytes, str]:
    """Разобрать ответ imap.fetch: тело письма и строку FLAGS."""
    if not msg_data:
        return b"", ""
    first = msg_data[0]
    if not isinstance(first, tuple) or len(first) < 2:
        return b"", ""
    meta, raw = first[0], first[1]
    flags = ""
    if isinstance(meta, bytes):
        flags = meta.decode("utf-8", errors="replace")
    elif isinstance(meta, str):
        flags = meta
    body = raw if isinstance(raw, bytes) else b""
    return body, flags


def _payload_to_text(payload: Any) -> str:
    if not payload:
        return ""
    if isinstance(payload, bytes):
        data = payload
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        return ""
    return data.decode("utf-8", errors="replace")


def _uid_str(uid: bytes | str) -> str:
    if isinstance(uid, bytes):
        return uid.decode("ascii", errors="replace")
    return str(uid)


def _connect_imap() -> imaplib.IMAP4_SSL:
    user = workspace_email()
    token = (get_settings().yandex_oauth_access_token or "").strip()
    context = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(_IMAP_HOST, _IMAP_PORT, ssl_context=context)
    imap.authenticate(
        "XOAUTH2",
        lambda _challenge: _xoauth2_plain(user, token).encode("utf-8"),
    )
    return imap


def _close_imap(imap: imaplib.IMAP4_SSL) -> None:
    try:
        imap.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        imap.logout()
    except Exception:  # noqa: BLE001
        pass


def _imap_precheck() -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.yandex_mail_enabled:
        return {"ok": False, "skipped": True, "reason": "YANDEX_MAIL_ENABLED=false"}
    if not settings.yandex_mail_imap_enabled:
        return {"ok": False, "skipped": True, "reason": "YANDEX_MAIL_IMAP_ENABLED=false"}
    if not token_available():
        return {"ok": False, "skipped": True, "reason": "no YANDEX_OAUTH_ACCESS_TOKEN"}
    return None


def imap_ping() -> dict[str, Any]:
    """Проверка IMAP + XOAUTH2 без чтения писем."""
    blocked = _imap_precheck()
    if blocked:
        return blocked
    try:
        imap = _connect_imap()
        try:
            status, data = imap.select("INBOX", readonly=True)
            if status != "OK":
                return {"ok": False, "error": "imap_select_failed", "detail": str(data)[:200]}
            total = int(data[0]) if data and data[0] else 0
        finally:
            _close_imap(imap)
        return {
            "ok": True,
            "mailbox": workspace_email(),
            "folder": "INBOX",
            "messages_total": total,
        }
    except imaplib.IMAP4.error as exc:
        detail = str(exc)[:300]
        hint = None
        low = detail.lower()
        if "auth" in low or "credentials" in low or "прав" in low:
            hint = (
                "OAuth scope mail:imap_ro + настройки Почты: IMAP и OAuth-токены; "
                "перевыпустите YANDEX_OAUTH_ACCESS_TOKEN"
            )
        return {"ok": False, "error": "imap_auth_failed", "detail": detail, "hint": hint}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def list_inbox(*, limit: int = 20, unseen_only: bool = False) -> dict[str, Any]:
    """Список входящих: только метаданные (from/subject/date), без тела."""
    blocked = _imap_precheck()
    if blocked:
        return blocked
    limit = max(1, min(limit, 100))
    try:
        imap = _connect_imap()
        try:
            status, _ = imap.select("INBOX", readonly=True)
            if status != "OK":
                return {"ok": False, "error": "imap_select_failed"}
            criteria = "UNSEEN" if unseen_only else "ALL"
            status, data = imap.search(None, criteria)
            if status != "OK":
                return {"ok": False, "error": "imap_search_failed"}
            uids = (data[0] or b"").split()
            uids = uids[-limit:][::-1]
            items: list[dict[str, Any]] = []
            for uid in uids:
                uid_label = _uid_str(uid)
                status, msg_data = imap.fetch(
                    uid_label,
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] FLAGS)",
                )
                if status != "OK" or not msg_data:
                    continue
                raw, flags_line = _imap_fetch_parts(cast(list[Any], msg_data))
                msg = email.message_from_bytes(raw)
                date_raw = msg.get("Date")
                date_iso = None
                if date_raw:
                    try:
                        date_iso = parsedate_to_datetime(date_raw).isoformat()
                    except Exception:  # noqa: BLE001
                        date_iso = date_raw[:40]
                items.append(
                    {
                        "uid": uid_label,
                        "message_id": _decode_mime(msg.get("Message-ID"))[:120],
                        "from": _redact_preview(_decode_mime(msg.get("From")), max_len=120),
                        "subject": _subject_safe(msg.get("Subject") or ""),
                        "date": date_iso,
                        "unseen": "\\Seen" not in flags_line,
                    }
                )
        finally:
            _close_imap(imap)
        return {
            "ok": True,
            "mailbox": workspace_email(),
            "count": len(items),
            "unseen_only": unseen_only,
            "items": items,
        }
    except imaplib.IMAP4.error as exc:
        return {"ok": False, "error": "imap_error", "detail": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def fetch_message(
    uid: str,
    *,
    include_body: bool = False,
    redact_body: bool = True,
    max_body_chars: int = 4000,
) -> dict[str, Any]:
    """Получить одно письмо по UID. Тело — только по явному запросу, с маскированием ПДн."""
    blocked = _imap_precheck()
    if blocked:
        return blocked
    uid_clean = (uid or "").strip()
    if not uid_clean.isdigit():
        return {"ok": False, "error": "invalid_uid"}
    try:
        imap = _connect_imap()
        try:
            status, _ = imap.select("INBOX", readonly=True)
            if status != "OK":
                return {"ok": False, "error": "imap_select_failed"}
            fetch_parts = "(BODY.PEEK[HEADER] FLAGS)"
            if include_body:
                fetch_parts = "(BODY.PEEK[] FLAGS)"
            status, msg_data = imap.fetch(uid_clean, fetch_parts)
            if status != "OK" or not msg_data:
                return {"ok": False, "error": "message_not_found", "uid": uid_clean}
            raw, flags_line = _imap_fetch_parts(cast(list[Any], msg_data))
            msg = email.message_from_bytes(raw)
            date_raw = msg.get("Date")
            date_iso = None
            if date_raw:
                try:
                    date_iso = parsedate_to_datetime(date_raw).isoformat()
                except Exception:  # noqa: BLE001
                    date_iso = date_raw[:40]
            result: dict[str, Any] = {
                "ok": True,
                "uid": uid_clean,
                "message_id": _decode_mime(msg.get("Message-ID"))[:120],
                "from": _redact_preview(_decode_mime(msg.get("From")), max_len=120),
                "to": _redact_preview(_decode_mime(msg.get("To")), max_len=120),
                "subject": _subject_safe(msg.get("Subject") or ""),
                "date": date_iso,
                "unseen": "\\Seen" not in flags_line,
            }
            if include_body:
                body_text = _extract_plain_body(msg)
                low = body_text.lower()
                if any(marker in low for marker in _FORBIDDEN_BODY_MARKERS) and redact_body:
                    body_out = _redact_preview(body_text, max_len=max_body_chars)
                    result["body_redacted"] = True
                elif redact_body:
                    body_out = _redact_preview(body_text, max_len=max_body_chars)
                    result["body_redacted"] = True
                else:
                    body_out = body_text[:max_body_chars]
                    result["body_redacted"] = False
                result["body"] = body_out
        finally:
            _close_imap(imap)
        return result
    except imaplib.IMAP4.error as exc:
        return {"ok": False, "error": "imap_error", "detail": str(exc)[:200], "uid": uid_clean}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
            "uid": uid_clean,
        }


def _extract_plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text = _payload_to_text(payload)
                    if charset.lower() not in ("utf-8", "utf8") and isinstance(payload, bytes):
                        try:
                            return payload.decode(charset, errors="replace")
                        except LookupError:
                            return text
                    return text
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    if isinstance(payload, bytes) and charset.lower() not in ("utf-8", "utf8"):
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            pass
    return _payload_to_text(payload)
