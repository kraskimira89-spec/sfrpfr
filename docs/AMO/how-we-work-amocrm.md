# Как работаем с amoCRM

> ⚠️ **РЕЗЕРВ (2026-08-29).** Рабочий стол: кабинет сотрудника.  
> Канон: [../ops/playbook-staff-cabinet-crm.md](../ops/playbook-staff-cabinet-crm.md).  
> Sync выключен: `AMOCRM_ENABLED=0`. Ниже — историческое описание интеграции.

**Чат / пакет:** [README.md](README.md)  
**ТЗ:** [tz-12-amocrm.md](tz-12-amocrm.md) · [ops-amocrm-setup.md](ops-amocrm-setup.md)

---

## Кратко (актуально)

**Кабинет сотрудника (admin)** — этапы, оплаты, LOSS, next_action, канбан.  
**amoCRM** — зарезервирована; не обязательна для лида с сайта.  
В amo **не** кладём сканы, СНИЛС, ИЛС, OCR.

---

## Исторические роли систем

| Система | Было задумано |
|---------|--------|
| Сайт / MAX / телефон | Вход обращения |
| SFRFR | Дело, кабинет, документы, оплаты |
| amoCRM | Операторская воронка (сейчас заменена admin) |

Канон: приложение SFRFR — истина по делу; amo при включении только mirror.

---

## Как течёт лид сейчас

```text
Форма на сайте / API
  → client + case в Supabase
  → (amo sync пропущен, если AMOCRM_ENABLED=0)
  → сотрудник работает в admin: реестр / канбан / финансы
```

---

## Что в коде (резерв)

- Интеграция: `src/sfrfr/integrations/amocrm/`
- CLI: `sfrfr amocrm-ensure-fields`, `sfrfr amocrm-sync` — имеют смысл только при `AMOCRM_ENABLED=1`

Без флага заявка в SFRFR создаётся; карточки в amo нет — это ожидаемо.
