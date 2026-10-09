# MCP: self-host Supabase (YC) через DBHub + OpenSSH -L

Канон БД: [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md).

**Прод:** `supabase.proverkastaza.ru` / ВМ `51.250.69.237` (прямой Postgres **`:5433`**, снаружи закрыт UFW/SG).

## Почему DBHub, а не `@supabase/mcp-server-supabase`

Официальный cloud-MCP требует hosted `project_ref` + PAT и к нашему self-host на YC не подключается.

## Почему не встроенный SSH DBHub / jump через app-VPS

- AdGuard VPN: трафик Node/Go SSH идёт с IP VPN → SG `:22` его режет.
- Исключение AdGuard для `ssh.exe` работает; для Cursor/node — нет.
- Jump `root@91.229.11.147` с VPN тоже часто timeout.

Поэтому лаунчер поднимает **OpenSSH LocalForward** (`ssh.exe`), а DBHub ходит только на `127.0.0.1:15433`.

## Что в репо

| Файл | Роль |
|------|------|
| `scripts/mcp-supabase-selfhost.cmd` | stdio-лаунчер: `ssh -L` + DBHub |
| `scripts/dbhub-supabase-selfhost.toml` | source + `execute_sql` **readonly** (без `ssh_*`) |
| `scripts/bootstrap_supabase_selfhost_mcp.ps1` | пишет `secrets/…env` с паролем с ВМ |
| `secrets/supabase-selfhost-mcp.env.example` | шаблон |

## Схема

```text
Cursor ──stdio──► mcp-supabase-selfhost.cmd
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   OpenSSH ssh.exe              DBHub readonly
   (исключение AdGuard)         → 127.0.0.1:15433
          │
          ▼
   sfrfr@51.250.69.237
          │  LocalForward
          ▼
   127.0.0.1:5433  (supabase-db на ВМ)
```

## Установка на этой машине

1. AdGuard VPN → исключения приложений → `C:\Windows\System32\OpenSSH\ssh.exe`.
2. SG `:22` пускает ваш домашний IP `146.158.1.12` (запасной вход — jump через App-VPS `91.229.11.147`). Выходы VPN `185.77.216.x` / `37.120.217.114` удалены 2026-09-25/26 — см. `docs/history/2026-09-25-yc-sg-ssh-cleanup.md`.
3. Bootstrap:

```powershell
.\scripts\bootstrap_supabase_selfhost_mcp.ps1
```

4. В `%USERPROFILE%\.cursor\mcp.json` уже должен быть сервер `supabase-selfhost` → этот `.cmd`.
5. Cursor → Settings → MCP → **Reload**.
6. Smoke: «покажи имена таблиц в public (лимит 20)».

**Не** класть пароль в `mcp.json`. **Не** открывать `:5433` в `0.0.0.0/0`.

## Локальный `DATABASE_URL` / dbt через туннель 15433

- В корневом `.env`: `DATABASE_URL=postgresql+psycopg://postgres:…@127.0.0.1:15433/postgres?sslmode=disable` (пароль — из `secrets/supabase-selfhost-mcp.env`), `DBT_HOST=127.0.0.1`, `DBT_PORT=15433`, `DBT_SSLMODE=disable`; роль dbt — `analytics_transformer`.
- Туннель: `ssh.exe -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15433:127.0.0.1:5433 sfrfr@51.250.69.237` (если порт уже слушает MCP — второй не нужен).
- Если `:22` не пускает текущий IP — тот же туннель с `-J sfrfr-vps` (правило SG «Admin SSH via app-VPS fallback»; бывает timeout — повторить).
- Проверка 2026-09-28: `select 1` OK, в `public` 32 таблицы.

## Ошибки

| Симптом | Действие |
|---------|----------|
| MCP discovery failed / tools unavailable | нет `.cmd` в ветке / не Reload; проверьте файл на диске |
| `OpenSSH tunnel failed` | исключение `ssh.exe`; SG `:22`; ключ `…UaTm` |
| `Missing secrets/…env` | `bootstrap_supabase_selfhost_mcp.ps1` |
| `Connection refused` на 15433 | туннель не поднялся; вручную: `ssh -L 15433:127.0.0.1:5433 sfrfr@51.250.69.237` |

## Не делать

- Коммитить `secrets/supabase-selfhost-mcp.env`.
- Открывать 5432/5433/8000 в интернет.
- Писать DDL/DML через MCP без явного подтверждения (readonly, но пароль — `postgres`).
