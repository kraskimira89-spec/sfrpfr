# 2026-10-09 — только self-host YC как БД проекта

Убраны ссылки и утилиты старого hosted Supabase из конфигурации и ops:

- `.env.example`, `apps/*/ .env.example`, CI → `https://supabase.proverkastaza.ru`
- удалены `supabase-cloud-*.md`, `mcp-supabase.cmd`, cutover-dump/cloud auth scripts
- канон БД: `docs/ops/supabase-selfhost-yandex-cloud.md`

Акты / переписка с прежним провайдером — вне git (юрархив).
