# QA: лид WP → API → amoCRM (ТЗ-10 P0 / ТЗ-12)

Цель: заявка с витрины создаёт дело в SFRFR и уходит в **amoCRM** (минимум контактов, без файлов).

## Цепочка

```text
WP форма (#kak-rabotat / WPForms)
  → POST /api/public/leads  (+ X-Public-Lead-Token, recaptcha_token при Enterprise)
    → client + case + checklist в Supabase
    → sync_case_to_amocrm (AMO_SUBDOMAIN + AMO_ACCESS_TOKEN)
    → thank-you / выбор канала (MAX | веб)
```

Код: `src/sfrfr/api/routes/public_leads.py`, `src/sfrfr/integrations/amocrm/`.  
Настройка: [docs/ops/amocrm-setup.md](../ops/amocrm-setup.md).

## Чеклист

| # | Шаг | Статус | Заметка |
|---|---|---|---|
| 1 | На VPS заданы `PUBLIC_LEAD_TOKEN`, при необходимости reCAPTCHA | [ ] | без токена на prod → 401/503 |
| 2 | `AMO_SUBDOMAIN`, `AMO_ACCESS_TOKEN`, `AMO_PIPELINE_ID`, `AMO_STATUS_ID` | [ ] | иначе `amocrm.skipped=true` |
| 3 | WP webhook/JSON бьёт в `https://api.proverkastaza.ru/api/public/leads` | [ ] | MU: `sfrfr-recaptcha-lead.php` |
| 4 | Отправка с мобилы и десктопа | [ ] | thank-you без приёма сканов |
| 5 | В ответе API есть `case_id` | [ ] | |
| 6 | В amoCRM видна сделка с полем `CASE_ID` | [ ] | этап «Новый лид» |
| 7 | Уведомление оператору (задача/сделка в amo) | [ ] | |
| 8 | В GTM/Метрику не уходят телефон/ФИО | [ ] | |

## Smoke (без создания боевого лида)

```powershell
curl -fsS https://api.proverkastaza.ru/health
# Без токена ожидаем 401 или 503 — эндпоинт жив:
curl -s -o NUL -w "%{http_code}\n" -X POST https://api.proverkastaza.ru/api/public/leads `
  -H "Content-Type: application/json" `
  -d "{\"full_name\":\"x\",\"contact\":\"y\",\"consent\":true}"
```

| Проверка | Статус | Дата |
|---|---|---|
| API health | [ ] | |
| POST `/api/public/leads` без токена → отказ (не 404) | [ ] | |
| Полный E2E с токеном + amoCRM | [ ] | нужен `PUBLIC_LEAD_TOKEN` / `AMO_*` |

## Блокеры

- Без `AMO_ACCESS_TOKEN` дело создаётся, CRM skip — это не «успешный» P0.
- Поля `CASE_ID` и др.: `sfrfr amocrm-ensure-fields`.

## Юрпроверка (вне scope агента)

Перед рекламой и оплатами нужно заключение юриста:

- оферта / индивидуальный заказ;
- формула success fee;
- согласия 152-ФЗ / ЗоЗПП.

Черновики в docs (монетизация / B2C) — не считать утверждёнными.
