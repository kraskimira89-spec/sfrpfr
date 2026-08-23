# Как работаем с amoCRM

**Чат / пакет:** [README.md](README.md)  
**ТЗ:** [tz-12-amocrm.md](tz-12-amocrm.md) · [ops-amocrm-setup.md](ops-amocrm-setup.md)

---

## Кратко

**amoCRM** — операторская воронка продаж и задач.  
**SFRFR (API + Supabase + кабинет)** — источник истины по делу, документам и оплатам.  
В amo **не** кладём сканы, СНИЛС, ИЛС, OCR.

---

## Роли систем

| Система | Зачем |
|---------|--------|
| Сайт / MAX / телефон | Вход обращения |
| SFRFR | Дело (`case_id`), кабинет, документы, статусы пайплайна |
| amoCRM | Сделка + контакт, этапы «продажи», задачи оператору, причины потерь, UTM/сегмент |
| Метрика / dbt / DataLens | Реклама и экономика (без ПДн дел) |

Канон маркетинга: приложение SFRFR — истина по делу; amoCRM ведёт продажи и задачи, файлы дела не хранит.

---

## Как течёт лид

```text
Форма на сайте / API
  → client + case в Supabase
  → sync в amo: сделка + контакт
  → в сделке CASE_ID = UUID дела SFRFR
  → cases.crm_external_id = ID сделки amo

Смена этапа в admin SFRFR
  → обновление сделки/полей в amo
```

Документы клиент грузит **только в кабинет** после согласия. Оператор в amo видит минимум для связи и ссылку в admin (`SFRFR_CASE_URL`), не архив сканов.

---

## Что уже в коде (ТЗ-12)

- Интеграция: `src/sfrfr/integrations/amocrm/`
- Поля сделки: `CASE_ID`, `SFRFR_CASE_URL`, `PIPELINE_STATUS`, `CHANNEL`, `SOURCE`, `CONSENT` (+ атрибуция из marketing foundation)
- CLI: `sfrfr amocrm-ensure-fields`, `sfrfr amocrm-sync --case-id …`
- Настройка аккаунта: [ops-amocrm-setup.md](ops-amocrm-setup.md)
- E2E-чеклист: [qa-lead-amocrm-e2e.md](qa-lead-amocrm-e2e.md)

Руками в UI amo: интеграция, токен, воронка/этап «Новый лид», права.  
Через API: поля, создание/обновление сделок.

---

## Как работать день за днём

1. **Лид пришёл** → в amo появляется сделка на этапе «Новый лид» с `CASE_ID`.
2. **Квалификация** — по playbook продаж (сегмент, ИЛС, трудовая; тяжёлый Word → отдельный счёт 100 ₽/разворот после осмотра сканов).
3. **Документы** — направляете в кабинет; в amo только статус/задача, не файлы.
4. **Продажа тарифа** — этапы и задачи в amo; факт оплаты и дело — в SFRFR.
5. **Потеря** — причина LOSS в amo (для разбора воронки).
6. **Маркетинг** — UTM/сегмент должны доезжать до полей сделки.

См. также: [sales-pipeline-amocrm.md](sales-pipeline-amocrm.md), [playbook-operator-amo-card.md](playbook-operator-amo-card.md), `docs/marketing-sales/playbook-sales-qualification.md`.

---

## Что нужно, чтобы «жить», а не только в доках

В `/opt/sfrfr/.env`: `AMO_SUBDOMAIN`, `AMO_ACCESS_TOKEN`, `AMO_PIPELINE_ID`, `AMO_STATUS_ID` → перезапуск API → тестовый лид по [qa-lead-amocrm-e2e.md](qa-lead-amocrm-e2e.md).

Владелец тестирует клиентский MAX с того же телефона **без** сделки в amo: [../ops/checklist-max-owner-test-no-amo.md](../ops/checklist-max-owner-test-no-amo.md).

Без токена sync может пропускаться (`skipped`) — заявка в SFRFR создаётся, но карточки в amo не будет (для prod лида с формы целевой сценарий — сделка обязательна).

---

## Связанные чаты

| Чат | Зона |
|-----|------|
| **AMO** | Настройка, sync, воронка, поля, E2E |
| Маркетолог | Гипотезы, UTM, отчёты; не дублировать ops amo |
| Бренд | Копирайт витрины, не CRM |
