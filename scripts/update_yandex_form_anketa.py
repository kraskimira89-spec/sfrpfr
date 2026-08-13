#!/usr/bin/env python3
"""Обновить Яндекс Форму-анкету: ФИО + телефон/email + существующие вопросы."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "https://api.forms.yandex.net/v1"
SURVEY_ID = "6a7db97670ad3712589c7456"
HEADER_ID = 131652585
KEEP_IDS = {
    HEADER_ID,
    131638039,
    131638040,
    131638041,
    131638048,
    131638049,
    131638050,
    131638051,
}


def _env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def main() -> int:
    load_dotenv(Path(".env"))
    load_dotenv(Path("secrets/yandex-forms.env"))
    token = _env("YANDEX_FORMS_OAUTH_TOKEN", "YANDEX_OAUTH_ACCESS_TOKEN")
    org_id = _env("YANDEX_FORMS_ORG_ID", "ORG_ID")
    if not token or not org_id:
        print("Нет токена или ORG_ID", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"OAuth {token}",
        "X-Org-Id": org_id,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        qs = client.get(f"{API}/surveys/{SURVEY_ID}/questions/", headers=headers)
        qs.raise_for_status()
        for item in qs.json()["pages"][0]["items"]:
            qid = int(item["id"])
            if qid in KEEP_IDS:
                continue
            dr = client.delete(
                f"{API}/surveys/{SURVEY_ID}/questions/{qid}/",
                headers=headers,
            )
            print(f"delete {qid} {dr.status_code} {(item.get('label') or '')[:40]}")

        fio_id = int(
            client.post(
                f"{API}/surveys/{SURVEY_ID}/questions/",
                headers=headers,
                json={
                    "type": "string",
                    "label": "ФИО",
                    "placeholder": "Иванов Иван Иванович",
                    "required": True,
                },
            ).json()["id"]
        )
        phone_id = int(
            client.post(
                f"{API}/surveys/{SURVEY_ID}/questions/",
                headers=headers,
                json={
                    "type": "string",
                    "label": "Телефон",
                    "placeholder": "+7 …",
                    "required": False,
                },
            ).json()["id"]
        )
        email_id = int(
            client.post(
                f"{API}/surveys/{SURVEY_ID}/questions/",
                headers=headers,
                json={
                    "type": "string",
                    "label": "Электронная почта",
                    "placeholder": "name@example.com",
                    "required": False,
                },
            ).json()["id"]
        )
        print(f"created fio={fio_id} phone={phone_id} email={email_id}")

        # Нельзя PATCH label у comment — API превращает его в string.
        # Заголовок оставляем как есть (KEEP_IDS), текст править только пересозданием.

        client.patch(
            f"{API}/surveys/{SURVEY_ID}/",
            headers=headers,
            json={
                "name": "Проверка стажа — анкета",
                "texts": {
                    "submit": "Отправить анкету",
                    "title": "Спасибо!",
                    "subtitle": (
                        "Анкета принята. При желании оставьте отзыв на Яндекс Картах:\n"
                        "https://proverkastaza.ru/otzyv/"
                    ),
                },
            },
        )

        order = [
            (HEADER_ID, 1),
            (fio_id, 2),
            (phone_id, 3),
            (email_id, 4),
            (131638039, 5),
            (131638040, 6),
            (131638041, 7),
            (131638048, 8),
            (131638049, 9),
            (131638050, 10),
            (131638051, 11),
        ]
        for qid, pos in order:
            mr = client.post(
                f"{API}/surveys/{SURVEY_ID}/questions/{qid}/move/",
                headers=headers,
                json={"page": 1, "position": pos},
            )
            print(f"move {qid} -> {pos}: {mr.status_code}")

        pub = client.post(f"{API}/surveys/{SURVEY_ID}/publish/", headers=headers)
        print(f"publish {pub.status_code}")

        final = client.get(f"{API}/surveys/{SURVEY_ID}/questions/", headers=headers)
        final.raise_for_status()
        Path("var/yandex-form-questions.json").write_text(
            json.dumps(final.json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for item in final.json()["pages"][0]["items"]:
            print(item["id"], item["type"], (item.get("label") or "")[:70])

    print("ok", f"https://forms.yandex.ru/cloud/{SURVEY_ID}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
