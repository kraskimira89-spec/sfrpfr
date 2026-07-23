# Обезличенные кейсы для RAG

Только файлы `CASE-YYYY-NNN.json` (+ опционально `.md`) без ПДн.

Статусы: `draft` → проверка эксперта → `verified` / `template` (в RAG) или `rejected`.

В RAG попадают **только** `verified` и `template`.

## CLI

```powershell
sfrfr knowledge-depersonalize-dir .\inbox\ --out .\cleaned\
sfrfr knowledge-import .\cleaned\dialog.md
sfrfr knowledge-import-deepseek conversations.json -n 5 --cleaned-dir storage/knowledge_inbox/cleaned
sfrfr knowledge-set-status CASE-2026-002 verified
sfrfr knowledge-list --rag-ready
```

## Контур улучшения (admin)

`POST /api/portal/admin/cases/{id}/knowledge-feedback` сохраняет заметку в БД
и создаёт/обновляет обезличенный `CASE-YYYY-NNN` с полем `ops_case_id`.
Список: `GET /api/portal/admin/knowledge-cases`.

Не коммитьте сырые диалоги DeepSeek с полными ПДн (`storage/knowledge_inbox/`).
