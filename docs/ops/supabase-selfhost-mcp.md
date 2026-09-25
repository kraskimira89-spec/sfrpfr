# MCP: self-host Supabase (YC) через DBHub

**Дата:** 2026-09-25
**Прод БД:** `supabase.proverkastaza.ru` / VM C `51.250.13.240` (прямой Postgres **`:5433`**)
**Не путать с:** официальным `https://mcp.supabase.com/mcp?project_ref=…` — это только **Supabase Cloud** (у нас legacy `frualvycousvvyjivybu`, rollback).

## Почему не `@supabase/mcp-server-supabase`

Пакет и `mcp.supabase.com` требуют **cloud** `project_ref` + PAT. Self-host на YC туда не подключается. Для Cursor используем **DBHub** (`@bytebase/dbhub`) + SSH jump на app-VPS.

## Что в репо

| Файл | Роль |
|------|------|
| `scripts/mcp-supabase-selfhost.cmd` | stdio-лаунчер (как Tracker/Wordstat) |
| `scripts/dbhub-supabase-selfhost.toml` | source + `execute_sql` **readonly** |
| `scripts/bootstrap_supabase_selfhost_mcp.ps1` | пишет `secrets/supabase-selfhost-mcp.env` из `DATABASE_URL` на VPS |
| `secrets/supabase-selfhost-mcp.env.example` | шаблон |
| `scripts/mcp-supabase.cmd` | **legacy Cloud** PAT — только drain/rollback, не прод |

## Схема

```text
Cursor ──stdio──► mcp-supabase-selfhost.cmd
                       │
                       ▼
                  DBHub (readonly)
                       │ SSH tunnel
                       ▼
              app-VPS 91.229.11.147 (root)
                       │ TCP
                       ▼
         VM C 51.250.13.240:5433  (supabase-db direct)
```

Studio по-прежнему: `ssh -L 8000:localhost:8000` на VM C (когда SSH allowlist пускает) — см. [production-access.md](./production-access.md).

## Установка на этой машине

```powershell
.\scripts\bootstrap_supabase_selfhost_mcp.ps1
```

В `%USERPROFILE%\.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "supabase-selfhost": {
      "command": "C:\\Users\\user\\Documents\\Cursor\\SFRFR\\scripts\\mcp-supabase-selfhost.cmd",
      "args": []
    }
  }
}
```

1. Cursor → Settings → MCP → **Reload**.
2. Статус `supabase-selfhost` — Connected.
3. Smoke: «покажи список схем в public (только имена таблиц)».

**Не** класть пароль в `mcp.json`. **Не** оставлять в `mcp.json` URL `mcp.supabase.com` с legacy `project_ref` как «прод».

## Блокеры (зафиксировано 2026-09-25 с этой сети)

| Проверка | Результат |
|----------|-----------|
| SSH `sfrfr@51.250.13.240` с ноутбука | timeout (SG `allowed_ssh_cidrs`) |
| SSH `root@91.229.11.147` (app-VPS) | OK |
| TCP VPS → `:5433` | **Connection refused** — прямой Postgres не слушает |
| TCP VPS → `:5432` | OPEN, но Supavisor: `ENOIDENTIFIER` (не для MCP/dbt) |
| Публичный IP админа | `185.77.216.28` — добавить в `allowed_ssh_cidrs` при работе с VM C |

Пока `:5433` down, MCP и dbt к YC **не** заработают. Канон портов: [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md) (`docker-compose.sfrfr-direct-pg.yml` в `COMPOSE_FILE`).

### Что сделать владельцу (вне Cursor)

1. **YC console / Terraform:** в `allowed_ssh_cidrs` добавить `185.77.216.28/32` (текущий IP), `plan`/`apply`. Не `0.0.0.0/0`.
2. **На VM C:** убедиться, что `supabase-db` публикует `0.0.0.0:5433→5432` (override), контейнер up.
3. С VPS: `nc -zv 51.250.13.240 5433` → open; `psql` по `DATABASE_URL`.
4. Reload MCP в Cursor.

## Ошибки

| Симптом | Действие |
|---------|----------|
| `Missing secrets/supabase-selfhost-mcp.env` | bootstrap.ps1 |
| SSH timeout на jump | ключ в `authorized_keys` на VPS; BatchMode |
| `Connection refused` :5433 | восстановить direct PG на VM C |
| `ENOIDENTIFIER` на :5432 | это Supavisor — **не** использовать для MCP; только :5433 |
| Агент ходит в Cloud `frualvycousvvyjivybu` | убрать URL из mcp.json; см. [supabase-cloud-drain-checklist.md](./supabase-cloud-drain-checklist.md) |

## Не делать

- Коммитить `secrets/supabase-selfhost-mcp.env`.
- Открывать 5432/5433/8000 в `0.0.0.0/0`.
- Писать DDL/DML через MCP без явного подтверждения (readonly включён, но пароль — `postgres`).
- Считать Cloud MCP «бесплатным self-host».

