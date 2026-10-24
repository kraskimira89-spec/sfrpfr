# 2026-10-24 — SFRFR-83: таблица статус → сообщение (follow-up #258)

**PR:** https://github.com/kraskimira89-spec/sfrpfr/pull/258 (без auto-merge)  
**Head:** см. последний push в ветку `fix/sfrfr-83-kit-ready-status`

## Quiet + полный комплект (`kind=receiving`, `working_question`)

| check_status | Сообщение (суть) |
|---|---|
| отсутствует / пусто | Проверка ещё не запущена |
| `queued` | Проверка ожидает запуска |
| `running` | Проверка выполняется |
| `failed` | По проверке возникла задержка: … Специалист разберётся и напишет сюда |
| `completed` | Проверка комплекта уже выполнена. Если итог не виден — напишите сюда |
| `needs_action` | По проверке требуется действие специалиста |
| иное / неизвестное | Статус проверки уточняем |

Общее: «Повторно присылать те же файлы не нужно.»  
**Нет** фразы «результат придёт в этот чат» (автодоставка не гарантирована).

## Перехваты `resolve` (не quiet-ветка)

| Условие | kind | Где |
|---|---|---|
| `result_current` + summary + `completed`/`needs_action` + result | `result_ready` | до quiet |
| без quiet, `queued`/`running` | `checking` | после quiet |
| без quiet, `failed` | `error` | после checking |
| quiet + любой check_status | `receiving` (status сохраняется) | quiet раньше checking/error |

Тесты: `test_quiet_kit_resolve_reply_by_check_status`, `test_failed_without_quiet_becomes_error_not_receiving`, `test_queued_without_quiet_becomes_checking`, `test_completed_with_result_beats_quiet`.

## Проверка

```text
pytest tests/unit/test_client_case_status_loop.py \
  tests/unit/test_brief_analysis_offer.py \
  tests/unit/test_max_diag_choice.py
→ 68 passed
```
