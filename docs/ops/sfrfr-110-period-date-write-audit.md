# Аудит write-путей даты / периода (E01 prep)

Дата аудита: 2026-10-24.  
SHA базы (#263 head): `4bb8c0d78bf07c993097e19f668ec341b114beb8`.  
Зависимость #261: `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01`.

**Объём:** инвентаризация и черновик события. Без миграций, без wire E01,
без утверждения «дата исправлена» в клиентском MAX.

## Вывод о достаточности хранения (итог аудита)

> **Данных пока недостаточно для честного E01-wire.**  
> Конкретные недостающие проверки: (1) API точечного изменения одной даты периода
> с `expected_version`; (2) разделение OCR / client_said / verified; (3) событие
> `period_date_corrected` с before/after не реализовано; (4) нет TrustedOpResult
> от реальной записи даты.  
> Существующие поля `case_pipeline_data.ils_periods` / `labor_periods` +
> `access_audit` **могут** принять минимальный контракт **кодом без миграции**
> (JSON period + audit payload), но **только после** появления авторизованного
> write-пути с версией. Отдельно согласуемая миграция **не обязательна на старте**,
> если version хранить в элементе JSON и подтверждение брать из upsert/ack.

Вариант: **достаточно изменения кода без изменения схемы** — как целевой минимум
после появления staff/job операции; **сейчас** — недостаточно (нет самой операции).

---

## 1. Инвентаризация путей записи

### P1. Полный snapshot пайплайна → Supabase

| Поле | Значение |
|---|---|
| Вход | `POST /cases/{id}/run` (staff sync ветка) |
| Авторизация | `principal.is_staff` + `require_case` |
| Поле | весь массив `ils_periods` / `labor_periods` (не одна дата) |
| Источник | результат локального `CaseOrchestrator` / extract |
| Запись | `CaseRepository.save_pipeline_snapshot` → `case_pipeline_data` upsert |
| Подтверждение | ответ upsert / возвращённый row; **нет** TrustedOpResult для одной даты |
| Конкурентность | last-write-wins по `case_id`; `updated_at` есть, optimistic lock нет |
| Повтор | повторный run перезаписывает весь snapshot |
| Последствия | findings/draft/analysis_notes в том же payload |
| Пробел | нет точечной коррекции; нет before/after одной даты; staff-only sync |

`файл::функция`: `src/sfrfr/api/routes/portal.py::run_case_pipeline` →  
`src/sfrfr/db/case_repository.py::save_pipeline_snapshot`

### P2. Локальный оркестратор (in-memory / cases.json)

| Поле | Значение |
|---|---|
| Вход | `CaseStore.run_until` / CLI / MAX `/run` / `api/routes/cases.py` |
| Авторизация | по контексту вызова (локальный store / max user record) |
| Поле | `ctx.ils_periods` / `labor_periods` целиком после extract |
| Источник | OCR → `extract_periods` (LLM или эвристика дат) |
| Запись | мутация `CaseContext` + persist `storage/cases.json` через CaseStore |
| Подтверждение | файл записан; не system-ack БД |
| Конкурентность | threading lock store; нет version периода |
| Повтор | повторный run пересчитывает периоды |
| Последствия | findings через `compare_ils_vs_labor_book` |
| Пробел | OCR/LLM extract ≠ verified; нет E01-события |

`файл::функция`:  
`src/sfrfr/ai/orchestrator.py::CaseOrchestrator.run_until`  
`src/sfrfr/ai/agents/extractor.py::extract_periods`  
`src/sfrfr/core/case_store.py::CaseStore.run_until` / `_ctx_to_dict`  
Вызовы: `handler.py` (~/run), `cli/main.py`, `api/routes/cases.py`, `portal.run_case_pipeline`

### P3. Запрос проверки без перезаписи периодов

| Поле | Значение |
|---|---|
| Вход | `request_pipeline_run` (клиент/staff) |
| Авторизация | case access |
| Поле | **даты не меняет** — статус + audit |
| Источник | — |
| Запись | `pipeline_status` / `access_audit` |
| Подтверждение | audit `pipeline_run_requested` |
| Пробел | нельзя использовать как «дата исправлена» |

`файл::функция`: `src/sfrfr/db/case_repository.py::request_pipeline_run`

### P4. Admin read-only отображение периодов

| Поле | Значение |
|---|---|
| Вход | admin case detail |
| Авторизация | staff |
| Поле | чтение `ils_periods` / `labor_periods` |
| Запись | **нет write** в найденном коде |
| Пробел | UI может показывать даты без verified-метки |

`файл::функция`: `src/sfrfr/api/routes/admin_portal.py` (чтение pipeline)

### P5. Анкета MAX (год рождения / стаж) — не период ИЛС

| Поле | Значение |
|---|---|
| Вход | `q:*` / текст анкеты |
| Поле | `q_answers` (experience и т.п.); **год рождения больше не спрашиваем** |
| Запись | intake store, не `case_pipeline_data.ils_periods` |
| Пробел | не путать с E01 «дата работы в деле» |

`файл::функция`: `questionnaire.py::apply_answer`

### P6. Клиентский MAX LLM / E05

| Поле | Значение |
|---|---|
| Вход | свободный текст |
| Запись даты | **нет** |
| Пробел | при Null LLM может **сказать** «исправлено» без записи (см. Null→LLM gap) |

---

## 2. Черновик события `period_date_corrected` (не реализовано)

Разделение слоёв:

| Слой | Содержимое | Не является |
|---|---|---|
| Команда | `op_id`, `case_id`, `period_ref`, `field`, `new_value`, `reason`, `actor_id`, `expected_version` | подтверждением сохранения |
| Подтверждённая запись | ack хранилища + `written_at` + `new_version` | текстом модели |
| Событие результата | ниже payload | командой |

### Минимальный payload события (черновик)

```json
{
  "event_type": "period_date_corrected",
  "op_id": "uuid",
  "case_id": "uuid",
  "period_ref": { "collection": "ils_periods|labor_periods", "index_or_id": "…" },
  "field": "date_from|date_to",
  "before": "1987-…|null",
  "after": "1985-…",
  "value_source": "ocr_extract|client_said|staff_verified|system_derived",
  "correction_basis": "string",
  "actor_id": "staff-or-job",
  "version_before": "n|null",
  "version_after": "n+1|null",
  "persisted_at": "iso-8601",
  "persist_ack_source": "db_write_ack|repository_update_ok|job_event_persisted",
  "dependent_results": ["findings", "draft", "client_facing_claims"],
  "dependents_status": "needs_recheck"
}
```

Привязка к существующему:

- хранение массивов — `case_pipeline_data.ils_periods` / `labor_periods`;
- след действия — `access_audit.action` (строка; структурированный payload пока нет);
- library ack — `TrustedOpResult` / `persist_flag_is_trusted` (#261).

**Один `op_id` без `persisted_at` + trusted ack ≠ «дата исправлена».**

---

## 3. Что нужно до E01-wire

1. Авторизованная операция точечной правки (staff/job).
2. Version на элементе периода (хотя бы в JSON).
3. Запись before/after + событие (audit или таблица — решить после code-path).
4. TrustedOpResult от реального upsert.
5. Инвалидация зависимых findings/draft без обещания пенсии.

До этого — только audit/docs (этот PR).
