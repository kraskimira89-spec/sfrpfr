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

1. OAuth-токен: https://oauth.yandex.ru (права на Tracker API).
2. Org id:
   - **Yandex Cloud:** `TRACKER_CLOUD_ORG_ID` (каталог/организация Cloud)
   - **Yandex 360:** при необходимости также `TRACKER_ORG_ID`
3. Создайте `secrets/yandex-tracker.env`:

```env
TRACKER_TOKEN=your_oauth_token
TRACKER_CLOUD_ORG_ID=your_cloud_org_id
# TRACKER_ORG_ID=your_org_id
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

- **uvx** (рекомендуется): [uv](https://github.com/astral-sh/uv) → `uvx yandex-tracker-mcp@latest`
- Если `uvx` нет — установите uv или клонируйте репо в `tools/yandex-tracker-mcp` (см. README там).

## Ошибки

| Симптом | Действие |
|---------|----------|
| `Missing secrets/yandex-tracker.env` | скопировать из `.example`, заполнить токен |
| `Connection closed` | не использовать PowerShell-лаунчер; только `.cmd` |
| 401 / org | проверить `TRACKER_CLOUD_ORG_ID` и scope OAuth |
| Очередь не найдена | создать очередь `SFRFR` в UI Трекера |

## Не делать

- Не коммитить `secrets/yandex-tracker.env`.
- Не хранить ПДн клиентов в названиях/описаниях задач.
- Не возвращать Notion MCP в рабочий процесс.

См. также: [yandex-tracker-ops.md](./yandex-tracker-ops.md), [yandex-tracker-greenfield-checklist.md](./yandex-tracker-greenfield-checklist.md).
