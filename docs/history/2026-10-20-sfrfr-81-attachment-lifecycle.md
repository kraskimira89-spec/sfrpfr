# 2026-10-20 — SFRFR-81: жизненный цикл вложения MAX

## Цель

Убрать ложное «Документы получили», когда байтов нет или файл недоступен специалисту из дела.

## Сделано

- Модуль `attachment_lifecycle`: стадии, durable JSON-store, дедуп, ретраи download, fail-soft `get_message(mid)`.
- Handler: без байтов → «проверяю» / «пришлите ещё раз», не processing_ack.
- Ack «получили» только если ingest + `document_is_staff_openable`.
- Portal: staff открывает `needs_reupload` / `local-pending` через `/api/portal/tmp-docs/{token}`.
- Метрика `max_false_ack_total`.

## Проверка

- Unit: `test_max_attachment_lifecycle`, media fallback, local_doc_download, quiet batch, local-first.
- Smoke владельца после deploy: файл → дело → открытие в admin; сценарий без url → просьба повторить.

## Не в этом PR

Шаг 2 (итог пачки), шаг 3 (карточка staff), D1/OCR.
