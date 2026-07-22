# Архитектура MVP

## Каналы и AI

- **Диалог с клиентом:** мессенджер [MAX](https://dev.max.ru/docs-api) (Bot API / webhook → наш backend).
- **LLM:** [Yandex AI Studio](https://aistudio.yandex.ru/) (OpenAI-compatible API).
- **Сайт:** WordPress на VPS; **API** на поддомене (`api.…`). DNS — reg.ru. См. [deploy-vps.md](deploy-vps.md).

```text
Клиент ──MAX──► api.taxi-doroga-dobra.ru/webhook
Витрина ─WP──► taxi-doroga-dobra.ru  (посадочная SFRFR)
API     ──────► Yandex AI Studio + OCR + audit
```

Поток статусов кейса:

`intake` → `documents_received` → `ocr_done` → `classified` → `extracted` →
`audited` → `draft_ready` → `human_review` → `completed` (+ `failed`).

Оркестратор: `sfrfr.ai.orchestrator.CaseOrchestrator`.
Сверка ИЛС↔трудовая — код (`core.audit_ils`), не LLM.
Хранилище MVP: `core.case_store.CaseStore` (`storage/cases.json`) + файлы в `storage/uploads/`.

API:

- `POST /api/cases` — создать кейс
- `POST /api/documents/upload` — файл в кейс
- `POST /api/cases/{id}/advance` — один шаг
- `POST /api/cases/{id}/run` — до `human_review`
- `POST /api/cases/{id}/complete` — HITL → `completed`
- `POST /api/integrations/max/webhook` — апдейты бота MAX

CLI: `sfrfr case-*`, `sfrfr max-subscribe`

## B2C-монетизация (частные клиенты)

Документы:

- [b2c-monetization-tz.md](b2c-monetization-tz.md)
- [b2c-monetization-model.md](b2c-monetization-model.md)
- [b2c-customer-journey.md](b2c-customer-journey.md)
- [b2c-architecture.md](b2c-architecture.md)
- [contracts/offer-draft.md](contracts/offer-draft.md)
- [contracts/individual-order-template.md](contracts/individual-order-template.md)

CRM: [Taganay «Клиентская база»](https://taganay.clientbase.ru/login.php).  
Google Sheets — только обезличенные метрики.  
Подача в СФР — клиентом самостоятельно. Success fee: 10% ЕДВ + 50% × 3 мес. прибавки, оплата через 2–3 мес. после результата.

Компоненты:

1. API (`sfrfr.api`) — кейсы, файлы, webhook MAX
2. DB (`sfrfr.db`) — Supabase/Postgres
3. OCR (`sfrfr.ocr`) — распознавание сканов
4. Core (`sfrfr.core`) — аудит и workflow
5. AI (`sfrfr.ai`) — агенты → Yandex AI Studio
6. Integrations (`sfrfr.integrations.max`) — бот MAX
7. Security (`sfrfr.security`) — согласие и шифрование ПДн
