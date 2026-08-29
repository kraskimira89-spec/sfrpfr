# AMO — пакет агента amoCRM (**РЕЗЕРВ**)

> **Статус с 2026-08-29:** amoCRM **выключена** (`AMOCRM_ENABLED=0`).  
> Операционная CRM: **кабинет сотрудника** — [playbook-staff-cabinet-crm.md](../ops/playbook-staff-cabinet-crm.md).  
> Код `src/sfrfr/integrations/amocrm/` **не удалять**. Документы ниже — на случай повторного включения.

## Быстрый старт (только если снова включаете amo)

1. `AMOCRM_ENABLED=1` + токены в `/opt/sfrfr/.env`
2. Новый чат Agent → имя **«AMO»**
3. Промпт: [prompt-agent-amocrm.md](prompt-agent-amocrm.md)

## Файлы пакета (архив процесса)

| Файл | Назначение |
|------|------------|
| [how-we-work-amocrm.md](how-we-work-amocrm.md) | Бывшие роли систем (обновить при включении) |
| [tz-12-amocrm.md](tz-12-amocrm.md) | ТЗ-12 |
| [ops-amocrm-setup.md](ops-amocrm-setup.md) | Настройка UI |
| [sales-pipeline-amocrm.md](sales-pipeline-amocrm.md) | Воронка / LOSS (канон причин перенесён в staff) |
| … | Остальные playbook’и — справочно |

## Жёсткие границы (актуальны всегда)

- В amo **нет** сканов, СНИЛС, ИЛС, OCR.
- Источник истины по делу и оплатам — SFRFR.
- Токены только в `secrets/` / VPS `.env`, не в git.
