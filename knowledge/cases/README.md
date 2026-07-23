# Обезличенные кейсы для RAG

Только файлы `CASE-YYYY-NNN.json` без ПДн.

Статусы: `draft` → проверка эксперта → `verified` / `template` (в RAG) или `rejected`.

Импорт:

```powershell
sfrfr knowledge-depersonalize-dir .\inbox\ --out .\cleaned\
sfrfr knowledge-import .\cleaned\dialog.md
sfrfr knowledge-set-status CASE-2026-002 verified
sfrfr knowledge-list --rag-ready
```

Не коммитьте сырые диалоги DeepSeek с полными ПДн.
