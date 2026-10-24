# SFRFR-111 цикл 4: тестовая БД + reclaim + browser UI

**Head #269:** `8cdb479e`  
**PR:** https://github.com/kraskimira89-spec/sfrpfr/pull/269  
Auto-merge **OFF**. Merge / deploy / prod-миграции / live MAX — **нет**.  
SFRFR-110 / SFRFR-111 — открыты.

## Окружение

| Параметр | Значение |
|---|---|
| OS | Windows 10 |
| Python | `.venv` 3.14.x |
| Тестовая БД | Docker `postgres:16-alpine` порт **55432** |
| DSN | `PRECHECK_PG_DSN=postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck` (локальный, не prod) |
| Доступ приложения | `PgRestShim` — те же `.table().update().eq()` CAS-цепочки, что у PostgREST-клиента |
| Подъём | `tools/precheck_job_pg/up.ps1` + `schema.sql` |

`no_dsn` у probe = URL не задан (конфиг), не «сервер недоступен».

## Команды и результаты

```powershell
$env:PRECHECK_PG_DSN="postgresql://sfrfr:sfrfr@127.0.0.1:55432/sfrfr_precheck"
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_precheck_handler_routing.py `
  tests/unit/test_precheck_job_lifecycle_and_callbacks.py `
  tests/unit/test_primary_doc_precheck.py `
  tests/unit/test_staff_document_check.py `
  tests/integration/test_precheck_job_pg.py -q
```

**Локально:** `68 passed` (unit + integration PG).

### Review-closure (отдельный прогон, не «общий счётчик»)

| Замечание ревью | Тест | Результат |
|---|---|---|
| Ошибка записи отказа ≠ «убираем» | `test_decline_save_failure_no_false_ok` | PASSED |
| Ошибка ask_staff ≠ «принят» | `test_ask_staff_save_failure_honest` | PASSED |
| После отказа/оплаты live gates | `test_decline_then_order_blocked`, `test_paid_after_result_blocks_order` | PASSED |
| status running ≠ «завершена» | `test_status_running_not_completed_text` | PASSED |
| upload/answer/order/summary | generator + `test_generator_payload_through_handler`; order = handoff/unavailable явно; legacy без check_id = `stale_missing_check_id` | PASSED |

## Job ownership (код)

- Claim **только** `queued` → `running` + `locked_by`
- Heartbeat продлевает `locked_at`
- Finalize / fail **только** владелец lease
- Reclaim только при stale `locked_at`; активный heartbeat не сбивается
- Старый worker после reclaim не перезаписывает результат

## PG сценарии (integration)

| Сценарий | Тест | Результат |
|---|---|---|
| Save/reload | `test_save_reload_result_same_meaning` | PASSED |
| Два обработчика | `test_two_handlers_only_one_claims` | PASSED |
| Stale reclaim + old cannot overwrite | `test_reclaim_after_stale_then_old_worker_cannot_overwrite` | PASSED |
| Долгая обработка / heartbeat | `test_heartbeat_prevents_false_reclaim` | PASSED |
| Результат есть, notify нет → догон флага | `test_notify_retry_without_recompute_flag` | PASSED |
| Process restart (subprocess) | `test_process_restart_subprocess_old_cannot_overwrite` | PASSED |
| Новый документ → stale fingerprint | `test_stale_fingerprint_marked_on_reload` | PASSED |

## Browser smoke

UI: `DocumentCheckPanel` показывает находки, ограничения и различие:

- результат сохранён;
- уведомление в очереди (`message_id`);
- skip / enqueue не подтверждён.

Полный E2E в живом admin против API в этом цикле — **чеклист** `docs/ops/sfrfr-111-precheck-browser-smoke.md` (без live MAX). Автоматический Playwright в репо отсутствует; прогон UI — следующий шаг при локальном admin.

## Live MAX

Отдельный пункт приёмки; **не** запускался. Handler + контролируемый `_reply` покрыты unit.

## CI

Проверить `gh run list --branch feat/sfrfr-primary-doc-precheck` на точном head после push. Предыдущие runs на более ранних SHA падали — см. отчёт после зелёного run.

## Блокеры SFRFR-111 (открыты)

1. Browser smoke на живом admin + API (не только panel markup).
2. Live MAX — только по разрешению.
3. CI green на head цикла 4.
4. Wiring `precheck:order` → реальный pay-link (сейчас честный unavailable/handoff).
