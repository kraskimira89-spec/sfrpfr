"""Аварийный приём заявок при недоступной БД: буфер JSONL на диске + уведомление сотрудникам.

Буфер лежит рядом с прочими runtime-файлами (``storage_local_path``/..), вне веб-доступа.
Доимпорт после восстановления БД — ``sfrfr.services.lead_emergency_import``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_MAX_DEDUPE_HOURS = 24
_SOURCE_LABELS = {"site": "с сайта", "max": "из чата MAX"}


def buffer_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "emergency_leads.jsonl"


def is_test_name(full_name: str | None) -> bool:
    return (full_name or "").strip().upper().startswith("ТЕСТ")


def load_emergency_leads() -> list[dict[str, Any]]:
    path = buffer_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            logger.warning("emergency_leads: битая строка пропущена")
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def rewrite_emergency_leads(rows: list[dict[str, Any]]) -> None:
    """Атомарная перезапись (отметки доимпорта)."""
    path = buffer_path()
    tmp = path.with_suffix(".jsonl.tmp")
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    with _lock:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)


def append_emergency_lead(record: dict[str, Any]) -> dict[str, Any]:
    """Дописать заявку одной строкой (O_APPEND, права 600)."""
    row = {
        "id": uuid.uuid4().hex,
        "received_at": datetime.now(UTC).isoformat(),
        "imported_case_id": None,
        "is_test": is_test_name(record.get("full_name")),
        **record,
    }
    path = buffer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with _lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    return row


def _has_recent_max_lead(max_user_id: str) -> bool:
    since = datetime.now(UTC) - timedelta(hours=_MAX_DEDUPE_HOURS)
    for row in load_emergency_leads():
        if row.get("source") != "max" or str(row.get("max_user_id")) != max_user_id:
            continue
        try:
            if datetime.fromisoformat(str(row.get("received_at"))) >= since:
                return True
        except ValueError:
            continue
    return False


def _notify_text(row: dict[str, Any]) -> tuple[str, str]:
    label = _SOURCE_LABELS.get(str(row.get("source")), "")
    lines = [
        f"Новая заявка {label} — база данных недоступна, заявка сохранена в аварийный буфер.",
        f"Клиент: {row.get('full_name') or 'имя не указано'}",
    ]
    if row.get("phone"):
        lines.append(f"Телефон: {row['phone']}")
    if row.get("email"):
        lines.append(f"Email: {row['email']}")
    if row.get("max_user_id"):
        lines.append(f"MAX user_id: {row['max_user_id']} (ответить можно в чате бота)")
    if row.get("channel"):
        lines.append(f"Канал: {row['channel']}")
    lines.append(f"Номер в буфере: {str(row.get('id'))[:8]}")
    lines.append("Свяжитесь с клиентом напрямую; в реестр дело попадёт после восстановления БД.")
    if row.get("is_test"):
        lines.insert(0, "[ТЕСТ]")
    subject = f"Проверка стажа: заявка {label} (БД недоступна)"
    return subject, "\n".join(lines)


def notify_emergency_lead(row: dict[str, Any]) -> dict[str, Any]:
    """Письмо на OPS_NOTIFY_EMAIL + лички ops-бота и канал специалистов (без групп из env)."""
    settings = get_settings()
    subject, body = _notify_text(row)
    result: dict[str, Any] = {"email": None, "max_sent": 0}

    to_addr = (settings.ops_notify_email or "").strip()
    if "@" in to_addr:
        try:
            from sfrfr.integrations.yandex_workspace.mail import send_mail

            result["email"] = send_mail(
                to=to_addr,
                template="custom",
                subject=subject,
                body=body,
                from_name="Проверка стажа",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("emergency lead email failed: %s", type(exc).__name__)

    try:
        from sfrfr.db.staff_roles import list_ops_dm_max_user_ids
        from sfrfr.integrations.max.ops_bot import get_ops_bot

        bot = get_ops_bot()
        if bot.available:
            targets: list[tuple[str | None, str | None]] = [
                (uid, None)
                for uid in list_ops_dm_max_user_ids(
                    extra_ids=settings.staff_login_approver_max_user_ids
                )
            ]
            channel = (settings.max_specialists_channel_chat_id or "").strip()
            if channel:
                targets.append((None, channel))
            for user_id, chat_id in targets:
                try:
                    if user_id:
                        bot.send_message(text=body, user_id=user_id)
                    else:
                        bot.send_message(text=body, chat_id=chat_id)
                    result["max_sent"] += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("emergency lead max notify failed: %s", type(exc).__name__)
    except Exception as exc:  # noqa: BLE001
        logger.warning("emergency lead max notify unavailable: %s", type(exc).__name__)
    return result


def capture_site_lead_db_down(**fields: Any) -> dict[str, Any]:
    row = append_emergency_lead({"source": "site", **fields})
    logger.warning("public lead buffered (db down) id=%s", row["id"][:8])
    row["notify"] = notify_emergency_lead(row)
    return row


def capture_max_lead_db_down(*, max_user_id: str, full_name: str | None) -> dict[str, Any] | None:
    """Новый клиент MAX без дела в БД: одна запись и одно уведомление на клиента за сутки."""
    mid = str(max_user_id or "").strip()
    if not mid or _has_recent_max_lead(mid):
        return None
    row = append_emergency_lead(
        {
            "source": "max",
            "max_user_id": mid,
            "full_name": (full_name or "").strip() or None,
            "channel": "max_miniapp",
            "consent": "max_pdn_gate",
        }
    )
    logger.warning("max lead buffered (db down) max=%s id=%s", mid, row["id"][:8])
    row["notify"] = notify_emergency_lead(row)
    return row
