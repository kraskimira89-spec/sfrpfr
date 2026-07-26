# ТЗ-12: интеграция amoCRM

**Статус:** MVP в коде (`src/sfrfr/integrations/amocrm/`)  
**Связано:** [01-architecture.md](01-architecture.md), [06-integrations-and-security.md](06-integrations-and-security.md)  
**Пошаговая настройка в UI amoCRM (исполнять по порядку):**  
➜ **[../ops/amocrm-setup.md](../ops/amocrm-setup.md)**

Официальные доки: [OAuth по шагам](https://www.amocrm.ru/developers/content/oauth/step-by-step) · [custom fields](https://www.amocrm.ru/developers/content/crm_platform/custom-fields) · [leads API](https://www.amocrm.ru/developers/content/crm_platform/leads-api)

---

## 1. Цель

Синхронизировать лиды и этапы дел SFRFR в amoCRM: **сделка + контакт**, связь по `case_id`, без файлов и чувствительных ПДн.

Источник истины по делу — FastAPI + Supabase. amoCRM — операторская воронка.

---

## 2. Принципы

1. Минимум контактов: ФИО, телефон/email, согласие (флаг), канал.
2. **Не передавать:** СНИЛС, паспорт, ИЛС, OCR, Storage URL, сканы.
3. Ключ связи: custom field сделки `CASE_ID` + `cases.crm_external_id` = ID сделки amo.
4. Taganay и amo могут работать параллельно, если оба сконфигурированы.

---

## 3. Где и что настраивать в amoCRM (сводка)

Полный текст с кликами — в [amocrm-setup.md](../ops/amocrm-setup.md). Кратко:

| Шаг | Где в amoCRM | Что |
|-----|--------------|-----|
| 0 | URL аккаунта | Поддомен → `AMO_SUBDOMAIN` |
| 1 | **амоМаркет** → ⋯ → **Создать интеграцию** | Интеграция «SFRFR», доступ к сделкам и контактам |
| 2 | Интеграция → **Ключи** → **Сгенерировать токен** | Долгосрочный Bearer → `AMO_ACCESS_TOKEN` (1 раз на экране) |
| 3 | **Настройки** → воронки сделок | Воронка «Проверка стажа», этап «Новый лид» → `AMO_PIPELINE_ID` / `AMO_STATUS_ID` |
| 4 | Поля сделок или CLI `amocrm-ensure-fields` | Коды `CASE_ID`, `SFRFR_CASE_URL`, `PIPELINE_STATUS`, `CHANNEL`, `SOURCE`, `CONSENT` |
| 5 | (вне amo) VPS `.env` | Прописать переменные, `systemctl restart sfrfr-api` |
| 6 | CLI + **Сделки** | Тестовый sync, проверка карточки |
| 7 | **Настройки** → пользователи | Доступ операторов к воронке |

---

## 4. Custom fields (сделка)

| code | Тип | Описание |
|------|-----|----------|
| `CASE_ID` | text | UUID дела SFRFR |
| `SFRFR_CASE_URL` | url | Ссылка в admin-кабинет |
| `PIPELINE_STATUS` | text | Зеркало `pipeline_status` |
| `CHANNEL` | text | `max_miniapp` / `web_cabinet` / `unset` |
| `SOURCE` | text | `wordpress` / `sfrfr` / … |
| `CONSENT` | checkbox | Согласие на связь |

Группа в UI: «SFRFR» (опционально).

---

## 5. Поток данных

```text
WP / API public leads
  → client + case в Supabase
  → sync_case_to_amocrm (contact + lead + custom_fields_values)
  → cases.crm_external_id = lead_id

Смена этапа в admin
  → push_case_to_amocrm (PATCH lead + поля)
```

---

## 6. Env (VPS)

```env
AMO_SUBDOMAIN=youraccount
AMO_ACCESS_TOKEN=
AMO_PIPELINE_ID=
AMO_STATUS_ID=
AMO_CASE_URL_TEMPLATE=https://{subdomain}.amocrm.ru/leads/detail/{id}
```

---

## 7. CLI

```bash
sfrfr amocrm-ensure-fields
sfrfr amocrm-sync --case-id <uuid>
```

---

## 8. Критерии приёмки

- [ ] Выполнены шаги 0–7 из [amocrm-setup.md](../ops/amocrm-setup.md)
- [ ] Без `AMO_ACCESS_TOKEN` sync возвращает `skipped`, дело создаётся
- [ ] С токеном: после лида в amo есть сделка с `CASE_ID` и контакт
- [ ] В admin отображается `crm_url`
- [ ] В payload нет СНИЛС/файлов
- [ ] Taganay при настроенном webhook работает независимо

---

## 9. Вне scope MVP

- Входящие webhooks amo → SFRFR
- Поле типа `file` в amo
- Автообновление OAuth refresh (при долгосрочном токене не нужно до даты окончания)
