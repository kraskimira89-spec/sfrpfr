# Playbook: реанимация дел (CRM + «мёртвые» лиды)

**Дата:** 2026-09-22 · доп. 2026-10-09 (канон документов MAX+кабинет)  
**Статус:** канон ops  
**CRM:** кабинет сотрудника ([playbook-staff-cabinet-crm.md](playbook-staff-cabinet-crm.md))  
**Смысл продаж:** [playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md) §5в  
**Волна «канал»:** [strategy-reactivate-150-channel-stuck-2026-10.md](../marketing-sales/strategy-reactivate-150-channel-stuck-2026-10.md)  
**Очередь Tracker:** **FUNNEL** — https://tracker.yandex.ru/FUNNEL-11 (`funnel-reactivation`)  
([playbook-funnel-ops.md](../TRACKER/playbook-funnel-ops.md))

---

## 1. Цель

Вернуть в движение:

1. **CRM-дела** — зависли на шаге (`waiting_on=client`, просрочен `next_action_at`, тишина после оффера/документов).
2. **«Мёртвые» лиды** — есть контакт MAX/сайт, но нет активного дела в канбане.
3. **Зависшие на канале** — заявка/чат есть, человек читает публичный канал и не возвращается в личный чат.

Не цель: массовая реклама, третье касание без сигнала, обещание перерасчёта.

---

## 2. Корзины

| Код | Кто | Критерий | Канал | Цель касания |
|-----|-----|----------|--------|--------------|
| **A** | CRM | `in_touch` / квалификация, тишина 3–14 д | MAX | На каком шаге |
| **B** | CRM | Ждём ИЛС / документы / чек-лист | MAX | Сервис §5в №1–№2 |
| **C** | CRM | Счёт DIAG без оплаты ≤21 д | MAX | Диагностика 3 000 ₽ |
| **D** | CRM | Оплачено, тишина с нашей стороны | staff task | Внутренний SLA |
| **E** | CRM | Архив / старый LOSS >30 д | по согласию | Win-back |
| **F** | любой | `do_not_contact` / «не беспокоить» | — | Не писать |
| **O** | orphan | есть `max_user_id`, нет открытого дела | MAX DM | «Нужна проверка» |
| **S** | site | case с сайта, 0 ответов staff > SLA | staff + MAX | Первый ответ |

Приоритет: **D → C → A/B → S → O → E**.

---

## 3. Расписание касаний

| Касание | Когда | Действие |
|---------|-------|----------|
| №1 | 5–7 дн. тишины (A/B/C) или 6 дн. после чек-листа | Сервис, не продажа |
| №2 | ещё ~7 дн. после №1 | Финал «не будем беспокоить» |
| После №2 | — | archive / «можно вернуться» |
| Окно | 10:00–19:59 МСК | иначе `quiet_hours` |
| Лимит | ≤1 сервисное / 48 ч на дело | `contact_policy` |

---

## 4. Автоматика

CLI: `sfrfr case-reactivation-due-tick`

| Режим | Флаг | Поведение |
|-------|------|-----------|
| План | `--dry-run` | JSON без отправки |
| Тик | timer 10:15 МСК | классификация → касание |
| Черновики | `CASE_REACTIVATION_AUTO_SEND=0` | без MAX |
| Отправка | `AUTO_SEND=1` | MAX outbox |

Автотик не трогает **E** и **F**. **D** — только задача сотруднику.

```bash
sfrfr case-reactivation-due-tick --dry-run
sfrfr case-reactivation-due-tick --limit 40
CASE_REACTIVATION_AUTO_SEND=1 sfrfr case-reactivation-due-tick --send --limit 40
```

Unit: `docs/systemd/sfrfr-case-reactivation.service` + `.timer`.

---

## 5. Недельный чеклист (FUNNEL)

```text
## Реанимация — неделя YYYY-MM-DD
### Автотик
- [ ] Timer active; sent / skipped / orphan
### Ручной разбор
- [ ] Канбан payment / docs / in_touch
- [ ] Корзина D и S
- [ ] После №2 → archive
### Запреты
- [ ] Нет F / перерасчёта / третьего касания
```

---

## 6. Шаблоны (кратко)

**A:** на каком шаге (ИЛС / документы / диагностика). Сканы в публичный канал не присылать; после согласия — личный чат или кабинет.

**B:** получилось ли заказать ИЛС → «ИЛС получил(а)».

**C:** напоминание диагностики 3 000 ₽ без обещания перерасчёта.

**O:** «Нужна проверка» — следующий шаг; сканы не сразу.

Полные тексты: код `src/sfrfr/services/case_reactivation.py` и clarity §5в.

---

## 7. Метрики

CLI JSON · `docs/marketing-sales/reports/funnel-reactivation-weekly.csv` · комментарии FUNNEL-11.

---

## 8. Связанные документы

- [strategy-reactivate-150-channel-stuck-2026-10.md](../marketing-sales/strategy-reactivate-150-channel-stuck-2026-10.md)
- [playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md)
- [playbook-funnel-ops.md](../TRACKER/playbook-funnel-ops.md)
- [strategy-ads-to-max-channel-2026-09.md](../marketing-sales/strategy-ads-to-max-channel-2026-09.md)
