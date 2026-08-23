# Yandex Tracker MCP (aikts) — Cursor

**Дата:** 2026-08-22  
**Пакет:** [yandex-tracker-mcp](https://pypi.org/project/yandex-tracker-mcp/) / репозиторий [aikts/yandex-tracker-mcp](https://github.com/aikts/yandex-tracker-mcp)

Задачи в Трекере из чата Cursor: создание issues, комментарии, поиск по очереди `SFRFR`.

## Что в репо

- Лаунчер: `scripts/mcp-yandex-tracker.cmd` (stdio; не PowerShell)
- Секреты: `secrets/yandex-tracker.env` (в `.gitignore`)
- Шаблон: `secrets/yandex-tracker.env.example`
- Опциональный клон для отладки: `tools/yandex-tracker-mcp/` (в `.gitignore`, см. `tools/yandex-tracker-mcp/README.md`)

## Ключи и OAuth

1. **Отдельный OAuth для Tracker** (токен Workspace mail/disk **не** подходит — будет HTTP 422).
2. https://oauth.yandex.ru — приложение с правами **Yandex Tracker**.
3. Org id — https://admin.yandex.ru или `tracker.yandex.ru/admin/orgs`:
   - **Яндекс 360 (proverkastaza.ru):** только `TRACKER_ORG_ID`
   - **Yandex Cloud:** только `TRACKER_CLOUD_ORG_ID`  
   Задавайте **одну** переменную, не обе.
4. Бootstrap (клон + pip + шаблон env):

```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\bootstrap_yandex_tracker_mcp.ps1
```

5. Заполните `secrets/yandex-tracker.env`:

```env
TRACKER_TOKEN=oauth_token_tracker
TRACKER_ORG_ID=your_360_org_id
# TRACKER_CLOUD_ORG_ID=  # только для Cloud org
```

Не коммитить реальный `.env`.

## Cursor: mcp.json

Файл: `%USERPROFILE%\.cursor\mcp.json` (глобально) или `.cursor/mcp.json` в проекте.

```json
{
  "mcpServers": {
    "yandex-tracker": {
      "command": "C:\\Users\\user\\Documents\\Cursor\\SFRFR\\scripts\\mcp-yandex-tracker.cmd",
      "args": []
    }
  }
}
```

Путь к `.cmd` — **абсолютный** под вашу машину. Секреты не кладём в `mcp.json` — только в `secrets/yandex-tracker.env`.

## После правки

1. Cursor → Settings → MCP → **Reload** (или Reload Window).
2. Статус `yandex-tracker` — Connected.
3. Smoke в чате: «Создай задачу в очереди SFRFR: smoke MCP».

## Зависимости лаунчера

1. **Рекомендуется:** `pip install -e tools/yandex-tracker-mcp` в `.venv` (делает `bootstrap_yandex_tracker_mcp.ps1`).
2. Лаунчер: `.venv\Scripts\python.exe -m mcp_tracker`.
3. Fallback: `uvx yandex-tracker-mcp@latest` ([uv](https://github.com/astral-sh/uv)).

## Ошибки

| Симптом | Действие |
|---------|----------|
| `Missing secrets/yandex-tracker.env` | скопировать из `.example`, заполнить токен |
| `Connection closed` | не использовать PowerShell-лаунчер; только `.cmd` |
| 401 / org | проверить `TRACKER_CLOUD_ORG_ID` и scope OAuth |
| Очередь не найдена | создать `SFRFR` в UI или POST `/v3/queues` с `lead` + `issueTypesConfig` (см. [yandex-tracker-ops.md](./yandex-tracker-ops.md)) |

## Не делать

- Не коммитить `secrets/yandex-tracker.env`.
- Не хранить ПДн клиентов в названиях/описаниях задач.
- Не возвращать Notion MCP в рабочий процесс.

См. также: [yandex-tracker-ops.md](./yandex-tracker-ops.md), [yandex-tracker-greenfield-checklist.md](./yandex-tracker-greenfield-checklist.md).
