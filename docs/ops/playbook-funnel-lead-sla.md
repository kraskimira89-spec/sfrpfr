# Ops: SLA первого ответа lead/qualify (FUNNEL-2)

**Задача:** [FUNNEL-2](https://tracker.yandex.ru/FUNNEL-2)  
**CRM:** staff cabinet (не amo)  
**Целевой SLA:** 30–60 мин в рабочие часы (Пн–Пт 10:00–19:00 МСК)

## Еженедельный ритм (без ПДн)

| День | Действие |
|------|----------|
| Пн | Проверить новые лиды в кабинете (стадия lead/qualify) |
| Ср | Выборка 5–10 дел: `created_at` лида → первый ответ в MAX/кабинете |
| Пт | Заполнить таблицу ниже; комментарий в FUNNEL-2 |

## Шаблон учёта (копировать в комментарий Tracker)

```text
## SLA lead/qualify — неделя YYYY-MM-DD

| # | case_ref (последние 4) | lead_at | first_reply_at | delta_min | OK? |
|---|------------------------|---------|----------------|-----------|-----|
| 1 | … | … | … | … | да/нет |

Вывод: …
Next step: …
```

**case_ref** — только обезличенный хвост из admin (не ФИО, не телефон).

## Триггеры эскалации

- > 60 мин в рабочее время → разбор дежурства / скрипта первого сообщения
- Пустой next step / дата в кабинете → напоминание оператору (FUNNEL-5)

## Канон

- `docs/TRACKER/playbook-funnel-ops.md`
- `docs/ops/playbook-staff-cabinet-crm.md`
- `docs/marketing-sales/playbook-sales-clarity-funnel.md`

## Закрытие FUNNEL-2

После 1 полной недели учёта + комментарий с выводом → resolution «Решен».  
Регулярный мониторинг — новые слоты FUNNEL-2 или эпик FUNNEL-1.
