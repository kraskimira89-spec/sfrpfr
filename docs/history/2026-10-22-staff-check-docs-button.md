# 2026-10-22 — кнопка «Проверить документы» в кабинете сотрудника

## Симптом

В admin после таблицы документов кнопка «Проверить документы» → notice
«Не удалось запустить проверку документов.» Результат не появляется.

## Root cause (проверено в открытой вкладке + CDP)

1. UI зовёт `POST https://api.proverkastaza.ru/.../request-review`.
2. Другие POST к API (`request-pipeline`, `telemost`) — 200.
3. Именно `request-review` → `Failed to fetch`, Performance `responseStatus: 0`,
   `transferSize: 0` (~0.7 s) — соединение обрывается без HTTP-тела.
4. В коде `enqueue_staff_document_check` сразу поднимал **daemon-thread** с
   `process_staff_document_check_job` (extract PDF и т.д.) **в процессе API**.
   На VPS (~2 GiB) это могло OOM/убить uvicorn **до** ответа клиенту → CORS/fetch
   падает, UI ловит catch.

## Фикс

- Enqueue только пишет `queued` (без in-process thread).
- `request_review` ставит `BackgroundTasks` **после** ответа HTTP.
- Ingest-worker по-прежнему подхватывает queued через
  `process_next_staff_document_check_job`.
- В UI catch показывает текст ошибки API, если есть.

## Не делали в этом PR

Усиление продающих текстов / пакет 5000 / касса. Секционное резюме противоречий
+ оффер 3000 — следующий шаг воронки (SFRFR-82) после зелёного smoke кнопки.
