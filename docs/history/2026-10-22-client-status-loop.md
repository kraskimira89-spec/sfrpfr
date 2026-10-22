# 2026-10-22 — разрыв статуса обработки и ответов бота после документов

**Ветка:** `fix/client-status-loop`
**Канон:** ТЗ-35 / 35a. E/F не открывать. C1 / SFRFR-69 / 81 не принимать и не закрывать. D2 не начинать.

## Проблема (код проверен)

После анкеты и пачки документов settle писал «Базовый комплект есть…», а обычный текст клиента уходил в `free_text_nudge` (шаг `whom`) с «Пришлите фото или PDF…». Exact action зацикливания: `free_text_nudge`. Дополнительно: `diag:yes` gated → безусловное «Пришлите документы…»; return_reminder при нулевом счётчике.

`build_final_message` — реестр типов, не запуск анализа. Timer settle ≠ задача краткой диагностики.

## Сделано

1. SoT [`client_case_status.py`](../../src/sfrfr/services/client_case_status.py): kinds receiving / checking / missing / error / kit_ready_no_analysis / result_ready / staff_active / no_docs; intent thanks / working_question / clarification.
2. Проводка: `_handle_client_free_text` → `case_status_reply`; `diag_choice` gated/paid; `return_reminder`; `MENU_STATUS`; честный текст settle.
3. При E/F закрытых не пишем «диагностика идёт».
4. Тесты: `test_client_case_status_loop.py` + усиление consent/restart/tech-split/event_id.

## Разделение проверки

| Категория | Статус |
|---|---|
| Код проверен | unit + synthetic handler |
| Интеграция проверена | сценарии status-loop / owner-pass / consent / diag |
| Живой MAX | **не** проверен — не отдавать владельцу до зелёного synthetic |
| Заблокировано | E/F; C1 smoke; D2; SFRFR-69/81 |

## Команды

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_client_case_status_loop.py `
  tests/unit/test_tz35_owner_pass.py `
  tests/unit/test_max_consent_gate_a2.py `
  tests/unit/test_max_diag_choice.py `
  tests/unit/test_max_doc_no_confirm_flow.py `
  --basetemp=tmp/pytest-status-loop -q
```
