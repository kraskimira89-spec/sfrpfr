# ТЗ-30: event-driven триггеры выдачи PDF и сервисных опросов

**Версия:** 1.0  
**Дата:** 2026-08-23  
**Статус:** MVP триггеры 1–4 в коде; опросы — см. [ТЗ-29](29-diagnosis-surveys.md)  
**Связано:** [ТЗ-28](28-diagnosis-secure-delivery.md) · [habr: согласия и уведомления](https://habr.com/ru/articles/1051866/)

---

## 1. Принцип

Не «авторассылка», а **машина состояний дела**: событие → смена статуса → **draft** сообщения → задача сотруднику → ручное утверждение отправки.

`published` ≠ `sent` ≠ `opened`.

Сервис по уже заказанной диагностике ≠ маркетинг (отдельное согласие).

---

## 2. Карта статусов

```text
diagnostic_result:
  draft → reviewed → published → delivered → opened
  → feedback_pending → feedback_received → closed
  (+ revoked)

notification_job:
  draft → approved → queued → sent → delivered
  | failed | cancelled | skipped

survey_campaign:
  scheduled → draft → approved → sent → completed
  | expired | cancelled
```

---

## 3. Policy: `can_contact`

Файл: `src/sfrfr/services/contact_policy.py`

Блокирует при: `do_not_contact`, отзыв ПДн, архив, hard bounce, канал недоступен, ручной диалог <48ч, лимит 1 сервисное / 48ч, marketing без consent.

Quiet hours: **20:00–09:00** Europe/Moscow → планировать на 10:00.

---

## 4. Триггеры MVP (1–4)

| № | Событие | Действие |
|---:|---|---|
| 1 | PDF published | secure link (hash, TTL 72ч, max_views=3); draft `result_ready`; задача сотруднику; audit |
| 2 | job approved | email: queued→sent; MAX: approved→mark_sent; result→`delivered` |
| 3 | link opened (не бот) | `viewed_at`; result→`opened`/`feedback_pending`; cancel unread; schedule clarity +48ч |
| 4 | ready sent >72ч, не открыт | один draft `result_unread` (idempotency); approve вручную |

Идемпотентность: `result:{id}:notification:result_ready|result_unread:v1`.

Prefetch/боты (`User-Agent`) **не** ставят `viewed_at`.

---

## 5. Слои

```text
Event handlers  — publish, open, approve, survey callback
Scheduler       — POST /admin/diagnosis-delivery/unread-tick
Policy engine   — can_contact()
Audit           — diagnostic_result_published, notification_sent, …
```

API failed jobs: `GET /admin/notification-jobs/failed`.

---

## 6. Rollout / rollback

1. Применить миграцию `20260823220000_diagnosis_delivery_state_machine.sql` (SFRFR).  
2. Smoke: publish → approve → open → unread-tick без открытия.  
3. Rollback: не удалять таблицы; отключить tick и UI approve; статусы обратносовместимы с прежними значениями + новые.

---

## 7. Приёмка

- [x] Draft без автоотправки  
- [x] can_contact на approve  
- [x] Open ≠ bot prefetch  
- [x] Unread max 1 + idempotency  
- [x] published → delivered → opened  
- [ ] P1: first_step / quality / email confirm page  
- [ ] P2: retry backoff 5m/30m/2h  
