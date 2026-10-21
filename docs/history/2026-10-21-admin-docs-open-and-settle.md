# 2026-10-21 — PDF из дела + settle без дублей + тихий бот при специалисте

## Симптомы (smoke)

- PDF из карточки дела не открывался.
- После Word-трудовой settle снова просил трудовую и перечислял дубликаты.
- Бот мешал специалисту (settle / LLM).
- UI толкал в «защищённый кабинет» вместо просмотра в admin.

## Исправления

1. **Staff preview:** `is_document_downloadable(..., allow_staff_preview=True)` для
   `security_check` / `quarantine` / `needs_reupload` / `manual_review`; signed-url
   и tmp-docs (PDF inline); `openSigned` с ошибкой в notice.
2. **Settle:** дедуп по `checksum_sha256`; строки «— тип»; skip если `staff_dialog_active`.
3. **DOCX:** `extract_text` через python-docx → `guess_from_bytes` видит трудовую.
4. **LLM:** при активном специалисте — `max_llm_staff_silent`, без ответа в чат.
5. **Admin UI:** кнопка «Открыть», тип/превью; убрана ссылка «защищённый кабинет».

## Проверено

- pytest: attachment_lifecycle, doc_no_confirm_flow, max_llm_chat
- ruff на изменённых py; `npx tsc --noEmit` в `apps/admin`
