# QA: лид WP → API → Taganay (ТЗ-10 P0)

Цель: заявка с витрины создаёт дело в SFRFR и уходит в CRM Taganay (минимум контактов, без файлов).

## Цепочка

```text
WP форма (#kak-rabotat / WPForms)
  → POST /api/public/leads  (+ X-Public-Lead-Token, recaptcha_token при Enterprise)
  → client + case + checklist в Supabase
  → sync_case_to_taganay (TAGANAY_WEBHOOK_URL)
  → thank-you / выбор канала (MAX | веб)
```

Код: `src/sfrfr/api/routes/public_leads.py`, `src/sfrfr/integrations/taganay/`.

## Чеклист

| # | Шаг | Статус | Заметка |
|---|---|---|---|
| 1 | На VPS заданы `PUBLIC_LEAD_TOKEN`, при необходимости reCAPTCHA | [ ] | без токена на prod → 401/503 |
| 2 | `TAGANAY_WEBHOOK_URL` (и опционально `TAGANAY_API_TOKEN`) | [ ] | иначе `taganay.skipped=true` |
| 3 | WP webhook/JSON бьёт в `https://api…/api/public/leads` | [ ] | MU: `sfrfr-recaptcha-lead.php` |
| 4 | Отправка с мобилы и десктопа | [ ] | thank-you без приёма сканов |
| 5 | В ответе API есть `case_id` | [ ] | |
| 6 | В Taganay видна карточка / внешний id | [ ] | по `case_id` |
| 7 | Уведомление оператору (Taganay/задача) | [ ] | |
| 8 | В GTM/Метрику не уходят телефон/ФИО | [ ] | |

## Smoke (без создания боевого лида)

```powershell
curl -fsS https://api.taxi-doroga-dobra.ru/health
# Без токена ожидаем 401 или 503 — эндпоинт жив:
curl -s -o NUL -w "%{http_code}\n" -X POST https://api.taxi-doroga-dobra.ru/api/public/leads `
  -H "Content-Type: application/json" `
  -d "{\"full_name\":\"x\",\"contact\":\"y\",\"consent\":true}"
```

| Проверка | Статус | Дата |
|---|---|---|
| API health (taxi) | [x] | 2026-07-26 |
| POST `/api/public/leads` без токена → отказ (не 404) | [x] | 2026-07-26 — HTTP 401 `invalid token` |
| Полный E2E с токеном + Taganay | [ ] | нужен `PUBLIC_LEAD_TOKEN` / CRM webhook |

## Блокеры

- DNS `proverkastaza.ru` ещё не резолвится — до cutover проверять `taxi-doroga-dobra.ru`.
- Без `TAGANAY_WEBHOOK_URL` дело создаётся, CRM skip — это не «успешный» P0.

## Юрпроверка (вне scope агента)

Перед рекламой и оплатами нужно заключение юриста:

- оферта / индивидуальный заказ;
- формула success fee;
- согласия 152-ФЗ / ЗоЗПП.

Черновики в docs (монетизация / B2C) — не считать утверждёнными.
