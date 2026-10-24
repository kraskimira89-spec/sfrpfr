# SFRFR-111: контракт первичной проверки документов (этап 1)

Трекер: родитель **SFRFR-111**, этап 1 = **SFRFR-112**.
Зависимость достоверных ответов: SFRFR-110 (не закрывает её DoD).
База ветки: `main`. Merge/deploy/live/миграции prod — отдельное разрешение.

## Аудит: куда делась кнопка и что уже есть

| Наблюдение | Факт |
|---|---|
| Кнопка «Проверить документы» | **Есть** в `apps/admin/.../case-work-route.tsx` (fallback и primary `request_docs_check`) |
| Вызов API | `admin-cabinet.tsx::requestReview` → `POST /api/portal/admin/cases/{id}/request-review` |
| Backend | `admin_portal.py::request_review` → `enqueue_staff_document_check` + `BackgroundTasks` |
| Job store | таблица `staff_document_check_jobs` |
| Worker | `process_staff_document_check_job` / poll из `document_ingest_worker` |
| Почему «не было видно результата» | Исторически: OOM при sync-анализе в HTTP; сейчас enqueue отложен. Результат — kit/OCR/типы, **не** сверка ИЛС↔трудовая; UI показывает `document_check`, но без клиентского резюме/MAX |
| Дубли кнопки в воронке | Убраны (history `2026-10-21-docs-dedup-work-route.md`); маршрут — `case_work_route.py` |

### Карта пути (reuse)

```text
UI CaseWorkRoute
  → POST request-review (admin_portal)
  → enqueue_staff_document_check (staff_document_check.py)
  → BackgroundTasks / ingest-worker
  → process_staff_document_check_job
  → _analyze_case_documents → build_check_result (+ brief)
  → job.result JSON
  → get_case_document_check → admin detail.document_check
```

Сверка периодов сейчас: `audit_ils.compare_ils_vs_labor_book` — **заглушка** (только empty-checks).
Платный оффер / MAX по результату precheck — **нет**.

## Контракт исходов (кодовый)

| Исход | Смысл | Рекомендация услуги |
|---|---|---|
| `discrepancies_found` | Конкретные расхождения источников | Можно предложить подробный анализ (с объяснением) |
| `needs_clarification` | Неоднозначность | Уточнить / дослать; услуга только если нужна углублённая проверка |
| `insufficient_documents` | Недостаточно для сопоставления | Дослать документы; **не** продавать анализ |
| `no_discrepancies_found` | В проверенном объёме расхождений нет | Сообщить границы; **не** навязывать услугу |
| `manual_review_required` | Авто-вывод ненадёжен | Сотрудник; не автопродажа |
| `failed` | Техсбой | Повтор/восстановление; не продажа |

«Нет расхождений» ≠ «пенсия верна».

### Поля сохранённого результата (минимум)

`check_id`, `case_id`, `documents_fingerprint`, `rules_version`, `started_at`/`finished_at`,
`status`/`outcome`, `areas_checked`, `findings[]`, `limitations[]`, `recommendation`,
`client_summary`, `stale`.

### Finding

`what`, `period_ref`, `source_a`, `source_b`, `discrepancy_type`, `extraction_confidence`,
`confirmed`, `needs_review`, `next_action`.

## Граница primary vs paid

- Primary: доступность/читаемость, извлечение периодов, сопоставление ИЛС↔документы о работе, резюме, следующий шаг.
- Paid подробный анализ: только при конкретной задаче из находок; цена/название из каталога; без суммы прибавки и автозаказа.
- Не править канонические даты staff; слова клиента — отдельный источник.

## Файл::функция (план изменений)

| Область | Цель |
|---|---|
| `services/primary_doc_precheck.py` (новый) | outcomes, compare, summary, recommendation |
| `core/audit_ils.py` | реальная сверка дат/пропусков/дублей |
| `services/staff_document_check.py` | встроить primary outcome в job.result |
| `api/routes/admin_portal.py::request_review` | exact case_id; не менять смысл enqueue |
| `services/primary_doc_precheck_max.py` (новый) | уведомление + callback-контур (controlled) |
| `apps/admin/.../DocumentCheckPanel` | показать outcome/резюме/устаревание |
| каталог офферов (существующий) | читать цену; не хардкодить |

## Остаток этапа 1

Проверено: кнопка и job-контур на месте; пробел — содержательная сверка + клиентский/MAX контур.
Далее: этапы 2–5 в коде на этой ветке.
