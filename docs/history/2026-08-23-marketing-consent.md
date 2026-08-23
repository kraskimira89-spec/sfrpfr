# 2026-08-23 — Marketing consent (MAX / e-mail)

## Зачем

Разделить согласие на ПДн, сервисные сообщения по обращению и **рекламные** сообщения в мессенджерах. Реклама — только при отдельном доказуемом согласии по каналу.

## Сделано

- Миграция `supabase/migrations/20260823180000_marketing_consents.sql`
- Политика `src/sfrfr/services/marketing_consent.py` + гейт в `max-reply`
- MAX: кнопки Да/Нет/Отписаться, команда СТОП
- Admin API: GET status, POST request; блок в чате дела
- WP-форма: необязательный checkbox маркетинга MAX
- Playbook: `docs/marketing-sales/playbook-marketing-consent.md`
- Черновик текста: `docs/contracts/marketing-consent-max-draft.md`
- Тесты: `tests/unit/test_marketing_consent.py`

## Не сделано / P1

- Запись consent с WPForms webhook при галочке
- Double opt-in страница / QR
- Полноценный журнал UI «Открыть журнал»
- Юр. утверждение текста согласия

## Трекер

[FUNNEL-5](https://tracker.yandex.ru/FUNNEL-5) (комментарий) или отдельная задача SFRFR по миграции на VPS.
