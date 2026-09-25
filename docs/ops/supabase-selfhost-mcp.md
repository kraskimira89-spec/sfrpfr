# MCP: self-host Supabase (YC) через DBHub + OpenSSH -L

**Дата:** 2026-09-25 (обновлено после cutover на `sfrfr-supabase-db-01`)
**Прод БД:** `supabase.proverkastaza.ru` / ВМ `51.250.69.237` (прямой Postgres **`:5433`**, снаружи закрыт UFW/SG)
**Не путать с:** официальным `https://mcp.supabase.com/mcp?project_ref=…` — это только **Supabase Cloud** (legacy `frualvycousvvyjivybu`).

## Почему не `@supabase/mcp-server-supabase`

Пакет и `mcp.supabase.com` требуют **cloud** `project_ref` + PAT. Self-host на YC туда не подключается.

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
| `scripts/mcp-supabase.cmd` | **legacy Cloud** — только drain/rollback |

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
2. SG `:22` пускает ваш домашний IP (`146.158.1.12` / `185.77.216.28` / `185.77.216.16`).
3. Bootstrap:

```powershell
.\scripts\bootstrap_supabase_selfhost_mcp.ps1
```

4. В `%USERPROFILE%\.cursor\mcp.json` уже должен быть сервер `supabase-selfhost` → этот `.cmd`.
5. Cursor → Settings → MCP → **Reload**.
6. Smoke: «покажи имена таблиц в public (лимит 20)».

**Не** класть пароль в `mcp.json`. **Не** открывать `:5433` в `0.0.0.0/0`.

## Ошибки

| Симптом | Действие |
|---------|----------|
| MCP discovery failed / tools unavailable | нет `.cmd` в ветке / не Reload; проверьте файл на диске |
| `OpenSSH tunnel failed` | исключение `ssh.exe`; SG `:22`; ключ `…UaTm` |
| `Missing secrets/…env` | `bootstrap_supabase_selfhost_mcp.ps1` |
| `Connection refused` на 15433 | туннель не поднялся; вручную: `ssh -L 15433:127.0.0.1:5433 sfrfr@51.250.69.237` |
| Агент ходит в Cloud `frualvycous…` | убрать URL из mcp.json |

## Не делать

- Коммитить `secrets/supabase-selfhost-mcp.env`.
- Открывать 5432/5433/8000 в интернет.
- Писать DDL/DML через MCP без явного подтверждения (readonly, но пароль — `postgres`).
