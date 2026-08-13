#!/usr/bin/env python3
"""Создать Яндекс Форму «подсказки к отзыву» через API.

Нужны: YANDEX_FORMS_ORG_ID + OAuth с forms:write
(YANDEX_FORMS_OAUTH_TOKEN или YANDEX_OAUTH_ACCESS_TOKEN).

Документация: https://yandex.ru/support/forms/ru/api-ref/examples
Playbook: docs/marketing-sales/playbook-yandex-form-review-prompts.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "https://api.forms.yandex.net/v1"
REVIEW_URL = "https://yandex.ru/sprav/82469923047/reviews/add/"

QUESTIONS: list[dict] = [
    {
        "type": "comment",
        "label": (
            "Подсказка к отзыву о сервисе «Проверка стажа». "
            "Отзыв — про нашу работу, не про решение СФР. "
            "Без паспортных данных и сканов."
        ),
        "header": True,
    },
    {
        "type": "enum",
        "label": "Чем мы помогли?",
        "widget": "radio",
        "required": True,
        "items": [
            {"label": "Сверили трудовую с выпиской ИЛС"},
            {"label": "Подготовили план / проект обращения"},
            {"label": "Перенесли трудовую в таблицу"},
            {"label": "Помогли разобраться с документами"},
            {"label": "Другое"},
        ],
    },
    {
        "type": "enum",
        "label": "Было ли понятно и спокойно общаться?",
        "widget": "radio",
        "required": True,
        "items": [
            {"label": "Да"},
            {"label": "В целом да"},
            {"label": "Местами сложно"},
        ],
    },
    {
        "type": "enum",
        "label": "Что было удобнее всего?",
        "widget": "radio",
        "required": True,
        "items": [
            {"label": "Личный чат MAX"},
            {"label": "Личный кабинет"},
            {"label": "Сроки ответа"},
            {"label": "Понятные шаги"},
            {"label": "Пока ничего из этого"},
        ],
    },
    {
        "type": "enum",
        "label": "Зачем обратились?",
        "widget": "radio",
        "required": False,
        "items": [
            {"label": "Сомневался(ась) в стаже"},
            {"label": "Помогал(а) родителю / родственнику"},
            {"label": "Перед пенсией"},
            {"label": "После отказа или ответа СФР"},
            {"label": "Другое"},
        ],
    },
    {
        "type": "enum",
        "label": "Понятна ли граница: мы готовим, подаёте вы, решает СФР?",
        "widget": "radio",
        "required": False,
        "items": [
            {"label": "Да"},
            {"label": "Стало понятнее"},
            {"label": "Пока не до конца"},
        ],
    },
    {
        "type": "string",
        "label": "Что улучшить? (одно предложение)",
        "placeholder": "Необязательно",
        "multiline": True,
        "required": False,
    },
    {
        "type": "enum",
        "label": "Порекомендовали бы близким при похожей ситуации?",
        "widget": "radio",
        "required": False,
        "items": [
            {"label": "Да"},
            {"label": "Скорее да"},
            {"label": "Нет"},
            {"label": "Пока рано говорить"},
        ],
    },
]


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
    if not token:
        print("Нет YANDEX_FORMS_OAUTH_TOKEN / YANDEX_OAUTH_ACCESS_TOKEN", file=sys.stderr)
        print(
            "Откройте и вставьте токен в secrets/yandex-forms.env:\n"
            "https://oauth.yandex.ru/authorize?response_type=token"
            "&client_id=4205bd720a8a45b787ddcf8c8a5cbc75",
            file=sys.stderr,
        )
        return 2
    if not org_id:
        print(
            "Нет YANDEX_FORMS_ORG_ID — API Форм требует организацию Яндекс 360.\n"
            "Скопируйте id: https://admin.yandex.ru/ или https://tracker.yandex.ru/admin/orgs\n"
            "Создайте форму вручную: docs/marketing-sales/playbook-yandex-form-review-prompts.md",
            file=sys.stderr,
        )
        return 2

    headers = {
        "Authorization": f"OAuth {token}",
        "X-Org-Id": org_id,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        create = client.post(
            f"{API}/surveys/",
            headers=headers,
            json={
                "name": "Проверка стажа — подсказки к отзыву",
                "texts": {
                    "submit": "Готово — открыть форму отзыва",
                    "title": "Спасибо!",
                    "subtitle": (
                        f"Скопируйте ответы своими словами в отзыв на Яндексе. "
                        f"Оценку выбираете вы. Ссылка: {REVIEW_URL} "
                        "Не указывайте СНИЛС, паспорт и суммы пенсии."
                    ),
                },
            },
        )
        if create.status_code != 201:
            print(f"create failed: {create.status_code} {create.text[:500]}", file=sys.stderr)
            return 1
        survey_id = create.json()["id"]
        print(f"survey_id={survey_id}")

        for question in QUESTIONS:
            added = client.post(
                f"{API}/surveys/{survey_id}/questions/",
                headers=headers,
                json=question,
            )
            if added.status_code != 201:
                print(
                    f"question failed ({question.get('label')}): "
                    f"{added.status_code} {added.text[:400]}",
                    file=sys.stderr,
                )
                return 1
            print(f"question ok id={added.json().get('id')} type={question['type']}")

        published = client.post(f"{API}/surveys/{survey_id}/publish/", headers=headers)
        if published.status_code != 200:
            print(f"publish failed: {published.status_code} {published.text[:400]}", file=sys.stderr)
            return 1

    public_url = f"https://forms.yandex.ru/cloud/{survey_id}/"
    out = {
        "ok": True,
        "survey_id": survey_id,
        "public_url_guess": public_url,
        "review_url": REVIEW_URL,
        "note": "Проверьте точный публичный URL в кабинете Форм и впишите в playbook.",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
