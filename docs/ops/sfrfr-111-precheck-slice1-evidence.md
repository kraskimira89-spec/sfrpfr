# SFRFR-111 срез 1: кнопка → job → результат → экран сотрудника

**Не** MAX, **не** платный офер, **не** merge/deploy/live.  
Комментарий Трекера #447 — контрольная точка SFRFR-110 (этапы 1–2), **не** ТЗ этого среза.

## Существующий контур (переиспользован)

| Компонент | Путь |
|---|---|
| Кнопка | `CaseWorkRoute` → `onRequestReview` → `POST …/request-review` |
| Job | `staff_document_check_jobs` + `enqueue_staff_document_check` |
| Worker | `BackgroundTasks` / `process_next_staff_document_check_job` |
| Stale | fingerprint комплекта vs текущие документы |

Новый pipeline **не** создавался. Добавлено: `primary_doc_precheck` → поля в `result` job → staff UI.

## Команды / SHA

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_primary_doc_precheck_slice1.py `
  tests/unit/test_staff_document_check.py -q --basetemp=tmp/pytest-precheck-s1
```

SHA и итог — в комментарии PR / Трекер после push.

## Ограничения

- InMemory unit ≠ PG/worker recovery (отдельный реестр).
- OCR/LLM sync в HTTP по-прежнему запрещены.
- #41/#42 — docs/HITL-контекст, код не перенесён слепо.
- #269 содержит MAX-слой; этот PR — вертикальный срез 1 без клиентской доставки.
