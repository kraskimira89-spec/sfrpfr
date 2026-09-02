# Шпаргалка оператора: новый лид (staff cabinet)

**CRM:** кабинет сотрудника (amo в резерв, `AMOCRM_ENABLED=0`)  
**Этап:** `new` / `in_touch` (канбан)  
**Полная инструкция:** [playbook-staff-cabinet-crm.md](playbook-staff-cabinet-crm.md) · [playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md)

---

## За 30 секунд

1. Открыть дело в **admin** → реестр или канбан.
2. **MAX user_id** в карточке → «Написать в MAX» (не ссылка на бота).
3. Первое сообщение — [playbook-operator-first-message-max.md](../AMO/playbook-operator-first-message-max.md).
4. В карточке: **next_action** + **next_action_at** + ответственный.

> Продаём ясность и план, не прибавку к пенсии. Первый оффер — **3 000 ₽**.  
> Сканы, СНИЛС, ИЛС — **только** MAX / кабинет клиента, не в заметках с ПДн.

---

## Первый контакт (SLA: 30–60 мин в рабочие часы)

| # | Действие |
|---|----------|
| 1 | Admin → карточка дела → «Написать в MAX» |
| 2 | Текст — [playbook-operator-first-message-max.md](../AMO/playbook-operator-first-message-max.md) |
| 3 | Скрипт clarity: за себя / родственник; пенсия; фокус; ИЛС; трудовая → оффер диагностики |
| 4 | **next_action** + дата в карточке (шаблон ниже) |
| 5 | Перевести колонку канбана → **in_touch** |

Учёт SLA: [playbook-funnel-lead-sla.md](playbook-funnel-lead-sla.md) · Tracker [FUNNEL-2](https://tracker.yandex.ru/FUNNEL-2).

---

## Дальше по воронке (вручную)

| После | Колонка / этап |
|-------|----------------|
| Квалификация + тип проблемы | in_touch |
| Оффер 3 000 ₽, ссылка в кабинет | payment |
| Оплата | payment → delivery |
| Документы в кабинете | docs / delivery |

Тарифы: диагностика **3 000 ₽** · подготовка **5 000 ₽** · сопровождение **8 000 ₽**. Без обещания перерасчёта.

---

## Шаблон next_action (копировать)

```text
Связь: [MAX] — [дата]
Кейс: [за себя / родственник]; пенсия: [уже / ещё нет]
Фокус: [ИЛС / север / отказ СФР]

Документы (только статус):
- ИЛС: нет | запрошен | в кабинете
- Трудовая / эл. сведения: …

Следующий шаг: …
Дата шага: …
Ответственный: …
```

Возражения / цена: [playbook-sales-clarity-funnel.md](../marketing-sales/playbook-sales-clarity-funnel.md) §4–§5.

---

## Можно / нельзя

| ✅ | ❌ |
|----|-----|
| Статусы документов в next_action | Сканы и ПДн в заметках |
| Смотреть документы в кабинете | СНИЛС, паспорт в открытом чате |
| LOSS с `loss_reason` | Отказ без причины |
| Цены 3/5/8; next step + дата | Обещание суммы пенсии / перерасчёта |
| Чек-лист при «дорого» как первый шаг | Скидка на эмоциях |
| «Ожидаем клиента» + 2 касания (§5в) | Дожим / LOSS сразу после молчания |

Разбор 5–10 диалогов: [playbook-funnel-clarity-dialog-review.md](playbook-funnel-clarity-dialog-review.md) · Tracker [FUNNEL-5](https://tracker.yandex.ru/FUNNEL-5).
