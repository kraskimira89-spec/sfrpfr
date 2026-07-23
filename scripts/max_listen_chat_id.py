"""Ждёт сообщение боту и печатает user_id / chat_id.

Запуск (PowerShell):
  $env:PYTHONPATH='c:\\Users\\user\\Documents\\Cursor\\SFRFR\\src'
  python scripts/max_listen_chat_id.py

Перед запуском откройте бота в MAX и сразу после старта скрипта
отправьте /start. Если webhook уже подписан, long poll может
ничего не получить — тогда смотрите логи API на VPS.
"""

from __future__ import annotations

import json
import sys

import httpx

from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.ssl_context import max_ssl_verify


def main() -> int:
    client = MaxBotClient()
    if not client.available:
        print("ERROR: MAX_BOT_TOKEN пуст в .env", file=sys.stderr)
        return 1

    print("Жду событие до 25 сек. Сейчас отправьте боту /start в MAX...")
    url = f"{client.api_base}/updates"
    params = {
        "timeout": 20,
        "limit": 50,
        "types": "message_created,bot_started",
    }
    with httpx.Client(timeout=35.0, verify=max_ssl_verify()) as http:
        resp = http.get(url, headers=client._headers(), params=params)
        print(f"status={resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text)
            return 1
        data = resp.json()

    print(json.dumps(data, ensure_ascii=False, indent=2))
    updates = data.get("updates") or []
    if not updates:
        print(
            "\nСобытий нет. Частые причины:\n"
            "1) не успели написать боту за время ожидания;\n"
            "2) webhook уже подписан — тогда /updates пустой, "
            "смотрите webhook-логи на VPS;\n"
            "3) для личной отправки достаточно user_id "
            "(POST /messages?user_id=...)."
        )
        return 0

    for upd in updates:
        msg = upd.get("message") or {}
        sender = msg.get("sender") or {}
        recipient = msg.get("recipient") or {}
        user_id = (
            sender.get("user_id")
            or recipient.get("user_id")
            or upd.get("user_id")
        )
        chat_id = recipient.get("chat_id") or upd.get("chat_id") or msg.get("chat_id")
        print("---")
        print(f"update_type: {upd.get('update_type')}")
        print(f"user_id: {user_id}")
        print(f"chat_id: {chat_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
