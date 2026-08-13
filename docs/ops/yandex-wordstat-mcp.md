# Yandex Wordstat MCP (Cursor)

**Дата:** 2026-08-13  
**Назначение:** частоты / похожие / динамика / регионы Wordstat v2 из чата Cursor.

## Что подключено

- Пакет: [`yandex-wordstat-mcp`](https://www.npmjs.com/package/yandex-wordstat-mcp) (Search API v2)
- Лаунчер: `scripts/mcp-yandex-wordstat.cmd` (stdio; PowerShell `.ps1` — только запасной)
- Секреты: `secrets/wordstat.env` (в `.gitignore`)
- Конфиг Cursor: `%USERPROFILE%\.cursor\mcp.json` → сервер `yandex-wordstat` → command на `.cmd`

## Ключи

1. Сервисный аккаунт в каталоге YC с ролью editor/admin (или минимум `search-api.webSearch.user`).
2. API-ключ со scope **`yc.search-api.execute`**.
3. В `secrets/wordstat.env`:

```env
YANDEX_SEARCH_API_KEY=AQVN…
YANDEX_FOLDER_ID=b1g…
```

Создать ключ (пример через API после IAM-токена SA):  
`POST https://iam.api.cloud.yandex.net/iam/v1/apiKeys` с `scopes: ["yc.search-api.execute"]`.

## После правки mcp.json

1. Cursor → Settings → MCP → `yandex-wordstat` → **Reload** (или Reload Window).
2. Статус должен быть Connected, не `Connection closed`.
3. Проверка в чате: «Покажи топ Wordstat по „проверка стажа“».

### Если `Error -32000: Connection closed`

- Не использовать PowerShell-лаунчер для MCP (ломает stdio). Канон: `scripts/mcp-yandex-wordstat.cmd`.
- Проверить, что есть `secrets/wordstat.env` с `YANDEX_SEARCH_API_KEY` и `YANDEX_FOLDER_ID`.
- В терминале: запустить `.\\scripts\\mcp-yandex-wordstat.cmd` — в stderr должно быть `Yandex Wordstat MCP server running on stdio`.

## Billing

Запросы Wordstat v2 тарифицируются через Yandex Cloud Search API. Смотреть квоты в консоли каталога.

## Не делать

- Не коммитить `secrets/wordstat.env` и API-ключи.
- Не класть ключи в git-tracked `.cursor/` проекта.
