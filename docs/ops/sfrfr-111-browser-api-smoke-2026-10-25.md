# SFRFR-111: browser/API smoke на supabase2 (2026-10-25)

## Контур

| Поле | Значение |
|---|---|
| Auth | GoTrue supabase2 — живой JWT `staff_bootstrap` (вкладка admin) |
| API | `https://api.proverkastaza.ru` |
| Дело | `d503add3-956a-48bc-91dc-1c3c3579e1a3` (synthetic `smoke-brief-*`) |
| Режим | read + POST `/request-review` — **без** live MAX / платежей |

## Ход

1. Открыта вкладка `admin.proverkastaza.ru/c/<case>` — сессия staff (JWT в `sb-supabase2-auth-token`).
2. UI **не** показывает кнопку «Проверить документы» — job `needs_action` → `primary_action=None` (это дизайн: ручная проверка).
3. Из сессии сделан POST `/api/portal/admin/cases/<id>/request-review`:

```json
{"ok":true,"message":"Проверка запущена.",
 "document_check":{"job_id":"d11b298f-ede2-4533-b2a3-6d4c6580c7a1",
 "status":"queued","deduped":false},
 "pipeline_status":"human_review"}
```

4. Job завершился: `status=needs_action`, `current_stage=done`, attempts=1.
5. GET case → `document_check.result`:

```text
originals_available:2 · text_extracted:0 · needs_manual_review:2
types_found: [ils, other]
next_action: "Проверьте вручную 2 документ(ов)…"
honest_brief: 3 items (1 docs + 2 needs_check), fingerprint ea96e89973e25cb0b9de8d2b
offer_diag_allowed: true · has_justified_discrepancy: true
```

## Доказательство

- Screenshot: вкладка 965f6e (кабинет + блок «Проверка документов»)
- Job rows: 2 × `needs_action` (старая `2b9ffa68`, новая `d11b298f`)

## Ограничения

- Это API-smoke из живой сессии, **не** Playwright UI-клик.
- Кнопки в UI нет при `needs_action` — сценарий «клик» для статуса `ожидает`/`failed`.
- Live MAX и платежи **не** включались.
- Тестовый staff login (GoTrue OTP) **не** отрабатывался — использована существующая сессия. Путь A–G из ТЗ остаётся.
