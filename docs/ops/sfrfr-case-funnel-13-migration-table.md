# Фаза 1: перенос блоков → 13 ступеней аккордеона

**PR:** ui/case-funnel-13-accordion · **без auto-merge / без merge при заморозке.**  
Тарифы, API, backend-статусы, напоминания — **не** менялись.

| Старый блок | Новая ступень | Перенесённые действия | Тест / примечание |
|-------------|---------------|----------------------|-------------------|
| DocumentsTable (`#case-docs-workplace`) | `documents` | таблица файлов, open signed | нет дубля workplace |
| CaseWorkRoute + DocumentCheckPanel | `documents` | «Проверить документы», маршрут 1→2→3 | кнопка в панели |
| Stage «Контакт» | `contact_consents` | MAX/email/согласие ПДн/представители | unit adapter |
| Stage «Документы» (kit-таблица) | `documents` | шаблоны ИЛС/труд, чек-лист docs | сохранено |
| Stage «Диагностика» | `precheck_summary` (+ PDF-инструменты временно здесь) | findings, notes, upload/publish PDF, delivery | partial |
| — | `full_analysis` | состояние + paymentKnown; новые действия not wired | stub |
| Stage «Оплата» | `analysis_payment` | заказы/ссылка/согласие услуги | paymentKnown ≠ один флаг |
| Stage «План» | `appeals_documents` | draft, сформировать проект | partial |
| — | `appeals_consent` / `appeals_payment` / `submission` / `follow_up` / `escalation_package` | — | NotWiredNote |
| Stage «Ответ СФР» | `response_review` | фиксация ответа | live |
| Stage «База знаний» | `closure` | feedback | live |
| Техжурнал ingest `<details>` | вне ступеней, внизу | IngestReviewPanel | роль `can_view_ocr` |
| Служебное · журнал | внизу стека | audit, pipeline | без изменений |
| Archive / Close | внизу после служебного | как раньше | — |

## Адаптер (контракт)

| Файл | Роль |
|------|------|
| `apps/admin/src/lib/case-funnel-types.ts` | ID, `StageStatus`, `StageAction`, `Loaded`, `LaterStageFacts`, `LEGACY_TO_NEW` |
| `apps/admin/src/lib/case-funnel.ts` | `buildFunnelStages` / `selectCurrentStage` / `FunnelView` |
| `apps/admin/src/lib/case-funnel-facts.ts` | `toFunnelFacts({ detail, laterStageFacts })` |

Слои: backend-факты → статус этапа; React-state → только раскрытие и формы (`busy` ≠ `in_progress`).  
`current` не является `StageStatus` — это `FunnelView.currentStageId`.  
Ступени 7–13 без `LaterStageFacts` → `sourceNotes` / `unknown`, не выдумка из `audit`.  
`payment` legacy → `null` (три коммерческих этапа).
