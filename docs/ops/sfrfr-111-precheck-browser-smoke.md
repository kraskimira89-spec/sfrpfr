# SFRFR-111 browser / API E2E — цикл 5

Синтетические данные. Live MAX не включать.  
Merge/deploy/реальные платежи — запрещены.

**Auth SoT:** GoTrue на **supabase2** (`https://supabase2.proverkastaza.ru`, health OK).  
Локальный precheck-harness `:55432` **без** Auth — для TRUNCATE/isolation; browser login — только через supabase2 + staff JWT/OTP тестового сотрудника.  
Доступ агента: `docs/ops/supabase2-agent-access-2026-10-24.md`.

## Компоненты

| Слой | Что используется | Подмена? |
|---|---|---|
| Admin UI | `apps/admin` кнопка «Проверить документы» → `POST …/request-review` | нет в целевом прогоне |
| API | FastAPI `admin_portal.request_review` → enqueue + BackgroundTasks | нет |
| Job | `process_staff_document_check_job_safe` | нет |
| Auth | GoTrue supabase2 | staff JWT (не anon) |
| БД приложения | supabase2 PostgREST | PG suite `:55432` = harness; prod SoT ≠ harness |
| MAX notify | enqueue | в E2E можно выключить доставку |

## Автоматизированный API-smoke (тот же HTTP, что UI)

```powershell
$env:PRECHECK_E2E_API_BASE = "http://127.0.0.1:8000"
$env:PRECHECK_E2E_STAFF_TOKEN = "<staff JWT>"
$env:PRECHECK_E2E_CASE_ID = "<synthetic-case-uuid>"
.\.venv\Scripts\python.exe tools\precheck_e2e\staff_document_check_api_smoke.py
```

Скрипт **не** подставляет готовый result: ждёт status completed/needs_action/failed с сервера.

## Ручной browser-протокол

```text
Вход сотрудника
→ карточка дела
→ «Проверить документы»
→ Network: POST /request-review → job_id
→ прогресс / F5
→ GET case → document_check.result.primary_precheck
→ находки, ограничения, следующий шаг, client_notify
```

## Варианты (заполняет исполнитель на стенде)

| # | Сценарий | Результат | SHA / дата |
|---|---|---|---|
| 1 | Новое дело без pipeline | _ожидает стенд_ | |
| 2 | Расхождение | _ожидает стенд_ | |
| 3 | Без расхождений | _ожидает стенд_ | |
| 4 | Неполный комплект | _ожидает стенд_ | |
| 5 | Техошибка | _ожидает стенд_ | |
| 6 | Повтор кнопки (dedupe) | _ожидает стенд_ | |
| 7 | F5 во время running | _ожидает стенд_ | |
| 8 | Новый документ → stale | _ожидает стенд_ | |
| 9 | Нет прав (403) | API-smoke умеет отметить forbidden | |

## Статус цикла 5 (код)

- Markup панели + API endpoint готовы.
- API-smoke скрипт добавлен.
- PostgREST стенд `:55433` + enqueue/dedupe/claim на реальном PostgREST — **да** (`test_precheck_job_postgrest.py`).
- Полный browser (вход сотрудника → UI): **блокер** — на стенде нет GoTrue/Supabase Auth; admin требует Bearer JWT. Критерий не снижаем.
- Не закрывать SFRFR-113/117 без заполненной таблицы browser-вариантов выше.
