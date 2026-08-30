# DeepSeek export: где лежит исходник (не в git)

**Не коммитить** `conversations.json` / `user.json` (ПДн). В `.gitignore`:
`storage/knowledge_inbox/`, `storage/deepseek_data-2026-07-23/`.

## Канон на диске ПК (2026-08-30)

Актуальная папка экспорта (вне дерева git):

```text
D:\user\Загрузки\deepseek_data-2026-07-23\conversations.json   ← источник правды для импорта
D:\user\Загрузки\deepseek_data-2026-07-23\user.json             ← не импортировать (email/PII)
```

Локальная копия рядом с репо (в `.gitignore`, не пушить):

```text
storage/deepseek_data-2026-07-23/conversations.json
storage/deepseek_data-2026-07-23/user.json
```

Историческая ссылка из чата 2026-07-23 (папки в Downloads уже нет):

```text
C:\Users\user\Downloads\deepseek_data-2026-07-23\…
```

Запись: `docs/history/recovered-chats-2026-07-26.md`.

## Что уже в репозитории (после импорта)

| Что | Где |
|-----|-----|
| Обезличенные кейсы | `knowledge/cases/CASE-2026-002`…`027` (`source_file: deepseek:…`) |
| Шаблон (не DeepSeek) | `CASE-2026-001` |
| Импортёр | `src/sfrfr/ai/knowledge/deepseek_export.py` |
| CLI | `sfrfr knowledge-import-deepseek <path-to-conversations.json>` |
| Cleaned MD | `storage/knowledge_inbox/` (gitignore, локально) |

## Повторный импорт (пример)

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr knowledge-import-deepseek "D:\user\Загрузки\deepseek_data-2026-07-23\conversations.json" -n 0 --cleaned-dir storage/knowledge_inbox/cleaned
```

`-n 0` / `limit=None` — все пенсионные диалоги по фильтру заголовка (см. код импортёра).
`user.json` не передавать.
