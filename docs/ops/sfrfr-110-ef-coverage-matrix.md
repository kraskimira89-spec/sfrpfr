# SFRFR-110: E/F покрытие (актуализация после date-op PR)

Канон: `docs/specs/client-ai-error-response-catalog.md`.
Полная матрица этапов 1–2 жила в docs-PR #267; на ветке date-op от `main` —
контрольный фрагмент для E01 и блокеров close.

| ID | Статус | Остаток |
|---|---|---|
| E01 write-op | Код операции + InMemory тесты; PG integration **не прогнан** | Нужен зелёный PG; нет HTTP/job wire; **нет E01-wire** |
| E01 client reply | GAP | После trusted adapter |
| E02–E04, E06–E21 | без изменений относительно этапа 1 | см. #267 matrix при merge docs |
| E05/F04 | WIRE_ISO в стеке #263 (не в этой ветке) | prod adapter |
| F01–F03 | LIB | wire |
| F04 | связан E05 | prod adapter |

**Close SFRFR-110:** нет.
