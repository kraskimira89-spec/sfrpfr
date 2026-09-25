# 2026-09-25 — MCP self-host Supabase

Официальный `mcp.supabase.com` ходит только в Cloud (`frualvycousvvyjivybu`), не в YC self-host.

- `scripts/mcp-supabase-selfhost.cmd` + `dbhub-supabase-selfhost.toml` (readonly)
- Bootstrap → `secrets/supabase-selfhost-mcp.env`
- После cutover на `51.250.69.237`: туннель **OpenSSH -L** (не jump VPS, не встроенный SSH DBHub) — иначе AdGuard VPN ломает discovery.
- Docs: `docs/ops/supabase-selfhost-mcp.md`
