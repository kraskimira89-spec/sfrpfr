# 2026-08-07 — мягкая просьба об отзыве в MAX после услуги

## Решение

После статуса `completed` бот один раз отправляет мягкую просьбу об отзыве в MAX.
Без давления («необязательно», «если не хотите — ничего писать не нужно») и **без авто-серии** напоминаний.

## Код

- `format_soft_review_ask_message` / `maybe_send_soft_review_ask` в `notifications.py`
- Идемпотентность: audit `max_review_ask_sent`
- URL: `YANDEX_BUSINESS_REVIEW_URL` / `settings.yandex_business_review_url`

## Документы

- ТЗ-19 §3, ops `yandex-business-reviews.md`, шаблоны `review-request-templates.md`
