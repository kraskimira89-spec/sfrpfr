# Playbook: сценарий «понял PDF и делает сам»

**Дата:** 2026-08-23  
**Статус:** канон ops + автоматизация draft→approve  
**Связано:** [обратная связь](playbook-diagnosis-feedback.md) · [архивный запрос](playbook-archive-request-prep.md) · [ТЗ-29](../specs/29-diagnosis-surveys.md) · [ТЗ-30](../specs/30-diagnosis-delivery-triggers.md) · [скрипты MAX](../../scripts/assets/copy/acts-alone-messages.md)

---

## 1. Принцип

Клиент ответил «всё понятно» (кнопка clarity / навигация **1**).  
Задача сервиса — **остаться полезным, не навязывая** подготовку 5 000 / сопровождение 8 000, пока нет конкретного объёма работ из PDF.

Исходящие касания: **авточерновик + due-tick → Approve сотрудником** (не тихий автоsend).

---

## 2. Этапы воронки

```text
PDF выдан
→ PDF открыт
→ clarity scheduled (+48ч) → draft → Approve → sent
→ ответ «Всё понятно» (clear)
→ стадия acts_alone (feedback_status=understood, pipeline_marker)
→ first_step scheduled (+10 дней) → due-tick → draft → Approve → sent
→ ответ: выполнил / сложность / отложил
→ quality (P1) или закрытие сервисного контура
```

Параллельно, если PDF открыт, а на clarity ещё нет ответа:

```text
opened + нет ответа clarity ≥ 2–3 суток
→ один draft «Удалось ознакомиться с результатом?» (idempotent)
→ Approve
```

Не путать с unread PDF (72ч без open) — это другой контур ТЗ-30.

---

## 3. Что говорить

После **clear** — только благодарность и пауза (см. `acts-alone-messages.md`).  
Через 10 дней — вопрос про **первый шаг плана**, не про оплату.  
Оффер 5 000 / 8 000 — только если в PDF есть объём и клиент сам просит помощь / first_step = blocked с темой архив/документы.

---

## 4. Поля в карточке

```text
feedback_status: understood
pipeline: acts_alone
first_plan_step_status: pending | done | blocked | deferred
difficulty_category: (если blocked)
Сопровождение запрошено: нет (по умолчанию)
```

---

## 5. Автоматика (код)

| Событие | Авто | Approve |
|---------|------|---------|
| Open PDF | schedule clarity +48ч | да (отправка) |
| clear | schedule first_step +10д; marker acts_alone | — |
| due survey tick | scheduled → draft + очередь staff | да |
| opened, no clarity answer 2–3д | draft acquaint reminder (1×) | да |
| first_step answers | обновить first_plan_step_status | — |

Quiet hours / `can_contact` / max 2 survey touches — как в ТЗ-29/30.

---

## 6. Когда выходить из сценария

- needs_help / question на clarity → контакт staff, отмена прочих survey.  
- first_step blocked + конкретный объём → playbook архива / подготовка 5k или 8k.  
- do_not_contact / suppression → стоп.
