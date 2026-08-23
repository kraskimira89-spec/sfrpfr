# ТЗ-28: безопасная выдача PDF-диагностики и сервисные уведомления

**Версия:** 1.0  
**Дата:** 2026-08-23  
**Статус:** MVP в коде (publish + draft + approve); напоминания/опрос — P1  
**Связано:** [ТЗ-27](27-diagnosis-pdf-feedback.md) · [ТЗ-30 триггеры](30-diagnosis-delivery-triggers.md) · [стандарт PDF](../marketing-sales/playbook-diagnosis-result-standard.md) · [feedback playbook](../marketing-sales/playbook-diagnosis-feedback.md) · [marketing consent](../marketing-sales/playbook-marketing-consent.md)

---

## 1. Цель

После подготовки результата система создаёт **контролируемые** сервисные уведомления, выдаёт PDF через защищённый кабинет / короткоживущую ссылку и помогает сотруднику собрать обратную связь.

Модель: **система готовит — сотрудник подтверждает**.  
PDF не уходит вложением в e-mail/MAX.

## 2. Критические ограничения

1. PDF не прикладывать к обычному e-mail и не отправлять в MAX.  
2. Хранить в непубличном Storage.  
3. В уведомлениях — только безопасная ссылка (кабинет или одноразовый URL).  
4. Не включать в тему, текст и URL: СНИЛС, паспорт, номер ИЛС, суммы пенсии, периоды, диагнозы, лишние ПДн.  
5. Сервис ≠ реклама; promo только с marketing consent.  
6. Автосообщения = **DRAFT**, отправка после approve сотрудником.  
7. `do_not_contact` / отзыв ПДн / permanent bounce → отмена будущих jobs.

E-mail — ПДн; обработка и защита по закону; реклама по сетям электросвязи — только с доказуемым предварительным согласием  
([РКН](https://rkn.gov.ru/treatments/chasto-zadavaemye-voprosy/zashchita-prav-subektov-personalnykh-dannykh/)).

---

## 3. Безопасная схема

```text
Специалист завершил диагностику
→ PDF в кабинете (doc_type=diagnosis_report)
→ publish → diagnostic_result.status=published
→ secure_share_link (token_hash) + notification_job(result_ready)=draft
→ сотрудник «Проверить и отправить»
→ клиент открывает → viewed_at + pdf_opened_at
→ draft result_unread (+72ч) если не открыл
→ feedback (ТЗ-27) после открытия / ответа
```

---

## 4. Сущности (БД)

| Таблица | Назначение |
|--------|------------|
| `diagnostic_results` | draft / reviewed / published / revoked; document_id; checksum; reviewed_by |
| `secure_share_links` | token_hash; expires_at; max_views; viewed_at; revoked_at; channel |
| `notification_jobs` | type; channel; status draft→approved→sent; requires_staff_approval |
| `diagnosis_feedback` | уже есть (ТЗ-27) |

Публичный URL шаринга: `/api/portal/diag-share/{token}` — **без** `case_id` в query.

---

## 5. MVP (этот релиз)

- [x] Publish PDF → `diagnostic_results` + draft `result_ready` (email и/или max)  
- [x] Secure link (hash токена, TTL, max_views)  
- [x] Admin: список jobs, approve/send, cancel  
- [x] Шаблоны e-mail/MAX без вложения PDF  
- [x] Просмотр по токену → `viewed_at` / `pdf_opened_at`, отмена unread  
- [x] При publish планировать draft `result_unread` на +72ч (не авто-send)  
- [ ] Admin UI кнопки в воронке (P1 — API готов)  
- [ ] Feedback buttons endpoint (ТЗ-27 P1)  
- [ ] Hard/soft bounce полный цикл (P2)

---

## 6. Приёмка

- PDF недоступен по постоянной публичной ссылке.  
- Уведомление создаётся draft и требует approve.  
- После открытия PDF unread-job отменяется.  
- При do_not_disturb / отзыве согласия jobs не уходят.  
- В URL/логах/шаблонах нет запрещённых ПДн.  
- Есть unit-тесты токенов, publish→draft, cancel unread.

Тексты: [`diagnosis-secure-delivery-messages.md`](../../scripts/assets/copy/diagnosis-secure-delivery-messages.md).  
Код: `src/sfrfr/services/diagnosis_delivery.py`, `src/sfrfr/db/diagnosis_delivery_repository.py`.
