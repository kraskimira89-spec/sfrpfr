#!/usr/bin/env python3
"""Восстановить сводку сценария MAX в ленте дела, если переписка не сохранилась."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sfrfr.core.config import get_settings
from sfrfr.db.case_messages_write import insert_case_message
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.max.case_chat_log import CALLBACK_LABELS

_LABELS = {
    "for_whom": {"self": "За себя", "relative": "Помогаю близкому"},
    "goal": {"operator": "Связаться с оператором", "check_experience": "Проверить стаж"},
    "pension_status": {"before": "До пенсии", "assigned": "Пенсия назначена"},
    "problem_type": {
        "ils_stazh": "ИЛС и стаж",
        "north": "Северный или льготный",
        "documents": "Документы",
        "sfr_refusal": "Отказ СФР",
    },
    "ils_available": {
        "yes": "Есть выписка ИЛС",
        "need": "Нужно получить ИЛС",
        "no": "Нет ИЛС",
        "unknown": "Не знаю, как получить ИЛС",
    },
    "employment_records_available": {
        "yes": "Документы о стаже: да",
        "partial": "Документы о стаже: часть",
        "no": "Документы о стаже: нет",
    },
    "device_preference": {
        "max": "Удобнее с телефона (MAX)",
        "web": "Удобнее с компьютера",
        "help": "Нужна помощь с устройством",
    },
    "status": {
        "handed_to_operator": "Передано оператору",
        "completed": "Сценарий завершён",
    },
}


def _intake_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_intake.json"


def _human(field: str, value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    key = f"intake:{field}:{raw}" if field in {"whom", "goal", "pension", "problem", "ils", "emp", "device"} else ""
    if key and key in CALLBACK_LABELS:
        return CALLBACK_LABELS[key]
    return (_LABELS.get(field) or {}).get(raw) or raw


def _summary_lines(rec: dict) -> list[str]:
    lines: list[str] = []
    for field in (
        "for_whom",
        "goal",
        "pension_status",
        "problem_type",
        "ils_available",
        "employment_records_available",
        "device_preference",
        "status",
    ):
        label = _human(field, rec.get(field))
        if label:
            lines.append(f"• {label}")
    started = (rec.get("started_at") or "")[:19].replace("T", " ")
    completed = (rec.get("completed_at") or "")[:19].replace("T", " ")
    if started:
        lines.append(f"• Начало в MAX: {started} UTC")
    if completed:
        lines.append(f"• Завершение сценария: {completed} UTC")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", help="Только это дело")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = _intake_path()
    if not path.exists():
        print(f"FAIL: no intake file {path}")
        return 1
    raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    rows = raw.get("rows") or {}
    sb = get_supabase_client()
    written = 0
    for _mid, rec in rows.items():
        if not isinstance(rec, dict):
            continue
        case_id = str(rec.get("case_id") or "").strip()
        if not case_id or len(case_id) < 32:
            continue
        if args.case_id and case_id != args.case_id:
            continue
        existing = (
            sb.table("case_messages").select("id").eq("case_id", case_id).limit(1).execute().data
            or []
        )
        if existing:
            continue
        bullets = _summary_lines(rec)
        if not bullets:
            continue
        body = (
            "Сводка сценария MAX (восстановлено автоматически — "
            "полная переписка с ботом не сохранилась в ленте из‑за сбоя схемы БД):\n"
            + "\n".join(bullets)
        )
        if args.dry_run:
            print(f"would backfill case={case_id[:8]}… lines={len(bullets)}")
            continue
        insert_case_message(
            {
                "case_id": case_id,
                "author_kind": "system",
                "author_user_id": None,
                "body": body[:4000],
                "channel_origin": "max",
            }
        )
        written += 1
        print(f"backfilled case={case_id[:8]}…")
    print(f"OK written={written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
