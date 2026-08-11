# QA: лид WP → API → amoCRM (ТЗ-10 P0 / ТЗ-12)

> **Пакет агента:** [README.md](README.md)  
> Канон QA: `docs/qa/lead-amocrm-e2e.md` — при правках синхронизировать оба.

Цель: заявка с витрины создаёт дело в SFRFR и **обязательно** уходит в **amoCRM** (минимум контактов, без файлов).

## Цепочка

```text
WP форма (#zayavka / WPForms) + канал (MAX|кабинет) + reCAPTCHA
  → MU wpforms_process → POST /api/public/leads
    → client + case + checklist в Supabase
    → sync_case_to_amocrm (обязателен lead_id; иначе 502/503 → форма не «успех»)
    → уведомление операторам в MAX (если заданы STAFF_LOGIN_APPROVER_*)
    → thank-you + ссылки MAX / кабинет
```

Код: `src/sfrfr/api/routes/public_leads.py`, `scripts/wp-mu-plugins/sfrfr-recaptcha-lead.php`.  
Настройка: [ops-amocrm-setup.md](ops-amocrm-setup.md) (канон: `docs/ops/amocrm-setup.md`).

## Чеклист

| # | Шаг | Статус | Заметка |
|---|---|---|---|
| 1 | На VPS заданы `PUBLIC_LEAD_TOKEN`, при необходимости reCAPTCHA | [ ] | без токена на prod → 401/503 |
| 2 | `AMO_SUBDOMAIN`, `AMO_ACCESS_TOKEN`, `AMO_PIPELINE_ID`, `AMO_STATUS_ID` | [ ] | иначе `amocrm_not_configured` |
| 3 | MU `sfrfr-recaptcha-lead.php` на `wpforms_process` | [ ] | при ошибке API форма не успешна |
| 4 | Отправка с мобилы и десктопа | [ ] | thank-you без приёма сканов |
| 5 | В ответе API есть `case_id` и `amocrm.lead_id` | [ ] | |
| 6 | В amoCRM видна сделка с полем `CASE_ID` | [ ] | этап «Новый лид» |
| 7 | Уведомление оператору в MAX / сделка в amo | [ ] | |
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

- Без `AMO_ACCESS_TOKEN` на production заявка отклоняется (это ожидаемо).
- Поля `CASE_ID` и др.: `sfrfr amocrm-ensure-fields`.
- Клиенту в MAX нельзя написать автоматически без `max_user_id` — пишем операторам + даём deep-link.

## Юрпроверка (вне scope агента)

Перед рекламой и оплатами нужно заключение юриста:

- оферта / индивидуальный заказ;
- формула success fee;
- согласия 152-ФЗ / ЗоЗПП.

Черновики в docs (монетизация / B2C) — не считать утверждёнными.
