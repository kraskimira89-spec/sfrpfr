# SFRFR-111 единая контрольная точка (2026-10-24)

**Тестируемый head #269:** после push этого коммита (см. `git rev-parse` / PR).  
История: hardening `05be1741` (61 passed) → цикл 4 PG `8cdb479e`/`834e992c` (68 passed, CI green) → этот срез (маршруты upload/answer/order + read-back флагов).

Auto-merge **OFF**. Merge / deploy / prod-миграции / live MAX — **нет**.  
SFRFR-110 / SFRFR-111 — открыты.

## Команды

```powershell
# unit + routes
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_precheck_handler_routing.py `
  tests/unit/test_precheck_job_lifecycle_and_callbacks.py `
  tests/unit/test_primary_doc_precheck.py `
  tests/unit/test_staff_document_check.py -q

# PG integration (после tools/precheck_job_pg/up.ps1)
$env:PRECHECK_PG_DSN="postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_precheck_job_pg.py -q
```

## CI

На `834e992c` — `success` (run 40110284910). После нового push — проверить повторно на точном head.

## БД / конкурентность / process restart (цикл 4, сохраняется)

| Сценарий | Статус |
|---|---|
| Save/reload | PASSED (PgRestShim CAS) |
| Dual claim | PASSED |
| Process restart subprocess | PASSED |
| Heartbeat vs reclaim | PASSED |
| Old worker after reclaim | PASSED |
| Notify догон без пересчёта | PASSED |
| Stale fingerprint | PASSED |

Путь: shim с теми же `.table().update().eq()` что PostgREST; prod DSN не использовался.

## Review-closure (hardening)

| Пункт | Тест | Статус |
|---|---|---|
| Decline fail ≠ «убираем» | `test_decline_save_failure_no_false_ok` | PASSED |
| Ask_staff fail ≠ «принят» | `test_ask_staff_save_failure_honest` | PASSED |
| Live gates после отказа/оплаты | decline→order / paid→order | PASSED |
| status ≠ «завершена» | `test_status_running_not_completed_text` | PASSED |
| Generator payload → handler | `test_generator_payload_through_handler` | PASSED |
| Flag ok = read-back | `test_patch_flags_requires_readback_match` | PASSED |

## Клиентские действия (SFRFR-116)

| Действие | Статус | Поведение |
|---|---|---|
| `upload` | **маршрут есть** | чат + link кабинет `#documents`; подпись «Как загрузить…» |
| `answer` | **частично** | показывает вопрос, пишет `precheck_awaiting_answer`; приём текста в handler — ещё связать (открыто) |
| `order` | **кабинет без автопокупки** | link в кабинет; подпись «Условия заказа в кабинете»; счёт не создаёт |
| `summary` | резюме/status по job | без ложного «завершена» |

## Browser smoke

Markup `DocumentCheckPanel` (находки/ограничения/notify).  
E2E живой admin — чеклист `sfrfr-111-precheck-browser-smoke.md`, **не закрыт**.

## Этапы SFRFR-113…117

| Этап | Статус |
|---|---|
| 113 job lifecycle | код+PG unit/integration; browser E2E открыт |
| 114 сопоставление/periods | реализовано; PG empty-pipeline в job path |
| 115 резюме/офер | gates + live recheck |
| 116 MAX | handler wired; upload/order кабинетом; answer awaiting — довязать текст; live MAX нет |
| 117 приёмка | не закрывать |

## Live MAX

Не запускался. Не дефект конфигурации — отдельное разрешение.
