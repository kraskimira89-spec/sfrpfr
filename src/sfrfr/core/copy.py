"""Публичные формулировки сервиса (единый источник)."""

from __future__ import annotations

# Эталон: scripts/assets/copy/submission-position.md
POSITION_FULL = (
    "Мы готовим документы, проект обращения и понятный план. "
    "Мы расскажем по шагам, но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. "
    "Решение о пенсии и перерасчёте принимает только СФР."
)

POSITION_SHORT = (
    "Мы готовим документы, проект обращения и план — расскажем по шагам, "
    "но подаёте через СФР или Госуслуги вы сами. "
    "Решение принимает СФР."
)

SUBMISSION_INSTRUCTION = POSITION_SHORT

WARNING = f"{POSITION_SHORT} Результат не гарантирован."

# К каждому счёту / pay-link (MAX, кабинет, напоминания).
PAYMENT_LEGAL_ACCEPTANCE = (
    "Оплата счёта означает согласие с обработкой персональных данных (ПДн), "
    "политикой cookies и условиями публичной оферты."
)

CONSENT_URL = "https://proverkastaza.ru/soglasie/"
COOKIES_URL = "https://proverkastaza.ru/cookies/"
OFFER_URL = "https://proverkastaza.ru/oferta/"

PAYMENT_LEGAL_ACCEPTANCE_WITH_LINKS = (
    "Оплата счёта означает согласие с обработкой персональных данных "
    f"({CONSENT_URL}), политикой cookies ({COOKIES_URL}) "
    f"и условиями публичной оферты ({OFFER_URL})."
)
