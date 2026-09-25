# 2026-09-25 — MCP self-host Supabase (DBHub + SSH jump)

## Зачем
Официальный `mcp.supabase.com` ходит только в Cloud (`frualvycousvvyjivybu`), не в YC self-host.

## Сделано
- `scripts/mcp-supabase-selfhost.cmd` + `dbhub-supabase-selfhost.toml` (readonly)
- `scripts/bootstrap_supabase_selfhost_mcp.ps1` → `secrets/supabase-selfhost-mcp.env`
- `docs/ops/supabase-selfhost-mcp.md`
- В `~/.cursor/mcp.json`: сервер `supabase-selfhost`; убраны Cloud supabase URL и чужой alwaysdata dbhub

## Блокер (живой замер)
- VPS → `:5433` Connection refused (direct PG не слушает)
- SSH на VM C с ноутбука timeout; публичный IP админа `185.77.216.28` — в SG
