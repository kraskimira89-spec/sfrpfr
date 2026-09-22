"""Лид-магнит: чек-лист документов, нужных для анализа дела.

Канон перечня: scripts/assets/copy/documents-checklist.md §1.
PDF рассылки: /pension-checklist-a4.pdf (PUB-6).
"""

from __future__ import annotations

import re

LEAD_MAGNET_PDF_URL = "https://proverkastaza.ru/pension-checklist-a4.pdf"
LEAD_MAGNET_PRINT_URL = "https://proverkastaza.ru/chek-list-dokumentov/pechat/"
LEAD_MAGNET_LANDING_URL = "https://proverkastaza.ru/chek-list-dokumentov/"

# Фразы с посадочной /chek-list-dokumentov/ и команды бота.
_REQUEST_PATTERNS = (
    re.compile(r"нужен\s+чек[-\s]?лист", re.IGNORECASE),
    re.compile(r"чек[-\s]?лист\s+документ", re.IGNORECASE),
    re.compile(r"^/checklist\b", re.IGNORECASE),
    re.compile(r"^/leadmagnet\b", re.IGNORECASE),
    re.compile(r"папк[аи]\s+пенсионн", re.IGNORECASE),
)


def is_lead_magnet_request(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    for pat in _REQUEST_PATTERNS:
        if pat.search(raw):
            return True
    return False


def build_lead_magnet_message(*, name: str | None = None) -> str:
    """Текст выдачи: перечень для анализа + ссылка на PDF."""
    greeting = "Здравствуйте"
    clean = (name or "").strip()
    if clean:
        greeting = f"Здравствуйте, {clean}"

    return (
        f"{greeting}!\n\n"
        "Направляю бесплатный чек-лист документов для анализа дела "
        "(проверка стажа по выписке ИЛС).\n\n"
        "Нужно сейчас для анализа:\n"
        "1) Выписка ИЛС (СЗИ-ИЛС) — актуальная, с датой формирования.\n"
        "2) Трудовая книжка (бумажная) или выписка из электронной трудовой.\n\n"
        "Паспорт и СНИЛС — для идентификации, если попросит специалист; "
        "цифрами в чат их не пишите.\n\n"
        f"PDF (одна страница A4):\n{LEAD_MAGNET_PDF_URL}\n\n"
        f"Рабочая тетрадь на 8 страниц:\n{LEAD_MAGNET_PRINT_URL}\n\n"
        "Когда выписка будет на руках, ответьте одним сообщением: "
        "«ИЛС получил(а)» или «Есть расхождение».\n\n"
        "Не отправляйте паспорт, СНИЛС, трудовую и выписку ИЛС в открытый канал. "
        "После согласия — личный чат MAX или кабинет на сайте.\n\n"
        "Решение о пенсии и перерасчёте принимает только СФР. "
        f"Сервис «Проверка стажа»: {LEAD_MAGNET_LANDING_URL}"
    )


def build_lead_magnet_email_body(*, name: str | None = None) -> str:
    """Тело письма на e-mail (тот же перечень, что в MAX)."""
    return build_lead_magnet_message(name=name)
