# 2026-09-22 — Upload documents + согласие ПДн один раз

## Вердикт
На проде schema lag + uploaded_by=max:… + silent local → 0 строк в documents.

## Сделано
- documents_schema.py: minimal insert + 
ormalize_uploaded_by
- MAX _ingest_max_file: без silent local, uploaded_by=None
- «Начать» = ПДн + cookies; inheritance sibling consents; кабинет без повторной кнопки
- Nudge: без ПДн → «Начать»; с ПДн → только оферта; DIAG promote pay_url после оферты
- work_map: DIAG can_pay без обязательного комплекта

## Проверка
_verify_document_upload.py на VPS ранее: ok + объект в pension-docs.
