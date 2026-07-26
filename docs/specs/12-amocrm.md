# ТЗ-12: интеграция amoCRM

**Статус:** MVP в коде (`src/sfrfr/integrations/amocrm/`)  
**Связано:** [01-architecture.md](01-architecture.md), [06-integrations-and-security.md](06-integrations-and-security.md), Taganay (параллельный адаптер)

## Цель

Синхронизировать лиды и этапы дел SFRFR в [amoCRM](https://www.amocrm.ru/developers/content/crm_platform/custom-fields): сделка + контакт, связь по `case_id`, без файлов и чувствительных ПДн.

Источник истины по делу — FastAPI + Supabase. amoCRM — операторская воронка.

## Принципы

1. Минимум контактов: ФИО, телефон/email, согласие (флаг), канал.
2. **Не передавать:** СНИЛС, паспорт, ИЛС, OCR, Storage URL, сканы.
3. Ключ связи: custom field сделки `CASE_ID` (text) + `cases.crm_external_id` = ID сделки amo.
4. Taganay и amo могут работать параллельно, если оба сконфигурированы.

## Custom fields (сделка)

Создаются CLI `sfrfr amocrm-ensure-fields` или вручную. Коды стабильные (`field_code` в API).

| code | Тип | Описание |
|------|-----|----------|
| `CASE_ID` | text | UUID дела SFRFR |
| `SFRFR_CASE_URL` | url | Ссылка в admin-кабинет |
| `PIPELINE_STATUS` | text | Зеркало `pipeline_status` |
| `CHANNEL` | text | `max_miniapp` / `web_cabinet` / `unset` |
| `SOURCE` | text | `wordpress` / `sfrfr` / … |
| `CONSENT` | checkbox | Согласие на связь |

Группа полей в UI: «SFRFR» (опционально).

## Поток

```text
WP / API public leads
  → client + case в Supabase
  → sync_case_to_amocrm (contact + lead + custom_fields_values)
  → cases.crm_external_id = lead_id

Смена этапа в admin
  → push_case_to_amocrm (PATCH lead + поля)
```

## Env (VPS `/opt/sfrfr/.env`)

```env
AMO_SUBDOMAIN=youraccount
AMO_ACCESS_TOKEN=
AMO_PIPELINE_ID=
AMO_STATUS_ID=
AMO_CASE_URL_TEMPLATE=https://{subdomain}.amocrm.ru/leads/detail/{id}
```

- `AMO_PIPELINE_ID` / `AMO_STATUS_ID` — стартовый этап «Новый лид» (числа из amo).
- Токен — long-lived из интеграции в кабинете разработчика amo.

## CLI

```bash
sfrfr amocrm-ensure-fields   # создать недостающие custom fields
sfrfr amocrm-sync --case-id <uuid>
```

## Критерии приёмки

- [ ] Без `AMO_ACCESS_TOKEN` sync возвращает `skipped`, дело создаётся.
- [ ] С токеном: после лида в amo есть сделка с `CASE_ID` и контакт с телефоном/email.
- [ ] В admin отображается `crm_url` на карточку сделки.
- [ ] В payload нет СНИЛС/файлов.
- [ ] Taganay при настроенном webhook продолжает вызываться независимо.

## Вне scope MVP

- Входящие webhooks amo → SFRFR (обратный sync этапов).
- Поле типа `file` в amo.
- OAuth refresh-автоматика (токен обновлять вручную/скриптом ops).
