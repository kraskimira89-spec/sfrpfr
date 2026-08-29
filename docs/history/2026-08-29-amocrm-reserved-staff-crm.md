# 2026-08-29 — amoCRM в резерв, CRM в кабинете сотрудника

## Решение

Этапы сделки и оплаты ведутся в admin SFRFR. amoCRM не удаляем: `AMOCRM_ENABLED=0`.

## Изменения

- флаг `amocrm_enabled` (default false); sync → `skipped: amocrm_disabled`
- публичный лид без hard-fail amo
- канбан в реестре; закрытие дела + `loss_reason`
- миграция `cases.loss_reason` / `closed_at`
- playbook: `docs/ops/playbook-staff-cabinet-crm.md`
- пакет `docs/AMO/` помечен как резерв

## Не делали

- Удаление `integrations/amocrm`
- Платные виджеты amo
