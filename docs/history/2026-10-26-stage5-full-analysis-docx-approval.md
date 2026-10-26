# 2026-10-26 — Этап 5: ИИ → Word → согласование

## Сценарий

Подробный разбор готовит ИИ; сотрудник проверяет; клиенту уходит **DOCX**
(почта или публичная ссылка на файл в Яндекс Диске `outgoing/`).
Клиент: «Согласовать» / «Есть замечания» / своя версия файла.
Этап 5 закрывается только после `full_analysis_approved`.

## Код

- `full_analysis_workflow.py` — версии и статусы (`storage/full_analysis/`)
- `full_analysis_docx.py` / `full_analysis_actions.py` — Word, почта, Диск
- Admin API: `/full-analysis/state|versions|…`
- UI: `FullAnalysisPanel` на ступени «Подробный анализ»
- Funnel facts: delivered только по audit `full_analysis_approved:*`

## Честно

Ошибка SMTP/Диска не ставит «отправлено». Публикуется один файл, не папка дела.
PDF-загрузка остаётся запасным каналом, не основным.
