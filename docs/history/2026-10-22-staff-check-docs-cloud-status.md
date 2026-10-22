# 2026-10-22 — «Failed to fetch» на «Проверить документы»: cloud_status

## Симптом

Кнопка в admin → notice «Не удалось запустить проверку документов: Failed to fetch».
`request-pipeline` при этом 200.

## Root cause (curl + api.err на VPS)

`POST .../request-review` → **HTTP 500** без CORS-заголовков → браузер маскирует
как `Failed to fetch`.

```text
postgrest.exceptions.APIError:
  column documents.cloud_status does not exist (42703)
```

`enqueue_staff_document_check` делал `.select(..., cloud_status, antivirus_status)`.
Колонки `cloud_status` в prod `documents` нет; для fingerprint нужны только
`id` + `checksum_sha256`.

## Фикс

Select в enqueue сужен до `id, checksum_sha256` (как в `get_case_document_check`).

## Проверено

- unit: `test_enqueue_does_not_process_inline` проверяет отсутствие `cloud_status`
  в select.
- Живой smoke кнопки — после deploy.
