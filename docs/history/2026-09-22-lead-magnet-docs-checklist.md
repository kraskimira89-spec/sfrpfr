# 2026-09-22 — лид-магнит: выдача перечня документов для анализа

## Что сделано

- Сервис `src/sfrfr/services/lead_magnet_checklist.py`: текст чек-листа (ИЛС + трудовая) + PDF.
- MAX: фразы «Нужен чек-лист документов» / `/checklist` → `action=lead_magnet_checklist`.
- Письмо WP MU `sfrfr-lead-magnet.php`: тот же перечень в теле e-mail.
- Тесты: `tests/unit/test_lead_magnet_checklist.py`.

## Проверено

- `pytest tests/unit/test_lead_magnet_checklist.py` — 4 passed.
