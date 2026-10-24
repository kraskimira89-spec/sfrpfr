# SFRFR-110: E/F покрытие (date-op #268)

Канон: `docs/specs/client-ai-error-response-catalog.md`.

| ID | Статус | Остаток |
|---|---|---|
| E01 write-op | Код CAS + snapshot CAS; **PG evidence блокер**; приёмка атомарности **не** закрыта | См. `sfrfr-110-period-date-atomic-boundary.md` |
| E01 client reply | GAP | После trusted adapter |
| E05/F04 | вне этой ветки | prod adapter |
| Close | **нет** | |

Операция: **реализована в коде / заблокирована для приёмки** до PG + решения по RPC.
E01-wire ещё не готов.
