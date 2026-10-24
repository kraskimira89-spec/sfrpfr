# QA: лид WP → API → staff CRM (канон с 2026-08-29)

**Задача:** [SFRFR-101](https://tracker.yandex.ru/SFRFR-101)
**Конфигурация:** `AMOCRM_ENABLED=0` — операционная CRM = кабинет сотрудника.
**Исторический чеклист с amo:** `lead-amocrm-e2e.md` (резерв при повторном включении).

Цель: заявка с витрины создаёт дело в SFRFR; staff видит его в реестре/канбане. Sync в amo **не** требуется.

## Цепочка

```text
WP форма (#zayavka / WPForms) + канал (MAX|кабинет) + reCAPTCHA
  → MU wpforms_process → POST /api/public/leads
    → client + case + checklist в Supabase
    → (amo skip при AMOCRM_ENABLED=0)
    → уведомление операторам в MAX (если STAFF_LOGIN_APPROVER_*)
    → thank-you + ссылки MAX / кабинет
```

Код: `src/sfrfr/api/routes/public_leads.py` (`_require_amocrm_lead` no-op при amo off).
Ops CRM: [playbook-staff-cabinet-crm.md](../ops/playbook-staff-cabinet-crm.md).

## Чеклист

| # | Шаг | Статус | Заметка |
|---|---|---|---|
| 1 | На VPS заданы `PUBLIC_LEAD_TOKEN`, при необходимости reCAPTCHA | [ ] | без токена → 401/503 |
| 2 | `AMOCRM_ENABLED=0` (текущий канон) | [ ] | amo-токены не обязательны |
| 3 | MU `sfrfr-recaptcha-lead.php` на `wpforms_process` | [ ] | |
| 4 | Отправка с мобилы и десктопа | [ ] | thank-you без сканов |
| 5 | В ответе API есть `case_id` | [ ] | `amocrm.lead_id` не обязателен |
| 6 | Дело видно в staff (реестр / канбан `new`) | [ ] | |
| 7 | Уведомление оператору в MAX (если настроено) | [ ] | |
| 8 | В GTM/Метрику не уходят телефон/ФИО | [ ] | |

## Smoke (без создания боевого лида)

```powershell
curl -fsS https://api.proverkastaza.ru/health
# Без токена ожидаем 401 или 503 — эндпоинт жив:
curl -s -o NUL -w "%{http_code}\n" -X POST https://api.proverkastaza.ru/api/public/leads `
  -H "Content-Type: application/json" `
  -d "{\"full_name\":\"x\",\"contact\":\"y\",\"consent\":true}"
```

| Проверка | Статус | Дата (UTC) |
|---|---|---|
| API health | [x] `status=ok` production | 2026-10-24T05:09:32Z |
| POST `/api/public/leads` без токена → отказ (не 404) | [x] **401** | 2026-10-24T05:09:32Z |
| Полный E2E с токеном → case в staff | [ ] | только по согласованию / тестовый lead |

## Блокеры

- Полный E2E с токеном — согласовать тестовый lead (без реальных ПДн клиента).
- Включение amo снова — только решение владельца (SFRFR-105 / AMO README).
