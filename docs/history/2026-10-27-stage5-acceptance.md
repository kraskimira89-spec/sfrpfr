# 2026-10-27 — Приёмка этапа 5 (#332 + hotfix)

## Опубликовано

| Поле | Значение |
|------|----------|
| Merge SHA (#332) | `cb24a1462634b996d7f3fa861adefbac78ad434a` |
| Deploy #332 | success — https://github.com/kraskimira89-spec/sfrpfr/actions/runs/40360328020 |
| Hotfix после приёмки | отдельный PR (stale v1, approve only sent, сброс отметок при правке) |

## DOCX-пример (обезличенный)

`tmp/acceptance-razbor-demo-v2.docx` (локально, не в git) — OOXML, периоды/источники из шаблона приёмки.

## Результаты проверок

| Проверка | Результат | Как проверено |
|---|---|---|
| Содержание разбора | PASS* | Unit + шаблон/ИИ: периоды, источники, без гарантий выплат. *Живой LLM на конкретном деле — смоук сотрудником. |
| Word | PASS | `test_full_analysis_docx`: PK/OOXML, текст версии совпадает с markdown |
| Отправка почта/Диск | PASS* | Код: вложение DOCX / publish одного файла `outgoing/`; ошибка → не «отправлено». *Живая почта/Диск — при включённых интеграциях. |
| Замечания клиента | PASS | `remarks` → не delivered; нужна новая версия |
| Новая версия | PASS | Правка текста → draft, сброс reviewed/sent; create v2 → v1 superseded |
| Подтверждение только актуальной | PASS | `stale_or_superseded`; approve только `sent` и `current_id` |
| Устаревшая ссылка v1 при v2 | PASS | workflow + funnel facts игнорируют approve:1 при version:2 |
| Ошибка доставки | PASS | `mark_delivery_error` не ставит sent |
| Файл клиента | PASS | `attach_client_revision` → remarks, не approved |
| Отдельно от обращений | PASS | этап 5 ≠ appeals_consent (этап 6) |

## Исправления по отклонениям (этот прогон)

1. Согласование устаревшей/не-current версии → `stale_or_superseded`.
2. Approve только после `sent` (не после одной проверки сотрудником).
3. Правка текста снимает reviewed/sent.
4. Funnel: delivered только по событиям актуального `version:N`.
