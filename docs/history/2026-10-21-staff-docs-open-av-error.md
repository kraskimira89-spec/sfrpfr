# 2026-10-21 — Staff «Открыть» и AV error (SFRFR-81)

## Причина

`is_document_downloadable(..., allow_staff_preview=True)` сначала резал любой
`antivirus_status` вне `{clean, not_configured, disabled}`. У PDF в
`manual_review` на тестовом деле статус `error` → `downloadable=false` →
кнопка «Открыть» disabled (мёртвая). DOCX с `needs_reupload` /
`not_configured` уже отдавались (signed-url + tmp-docs 200 в access-логе).

## Исправление

- Staff preview: блокировать только `infected`/`malicious`; `error`/`pending`
  разрешены для статусов quarantine/needs_reupload/manual_review/security_check.
- tmp-docs: `mime_verified` + `as_attachment` в токене; query `as_attachment`
  на signed-url для «Скачать».
- Admin UI: PDF Открыть+Скачать; прочее — Скачать; при блоке — текст причины,
  не disabled-кнопка без пояснения.

## Проверено

- unit: `test_staff_document_signed_url`, staff preview AV error
- ruff; `npx tsc --noEmit` в `apps/admin`
