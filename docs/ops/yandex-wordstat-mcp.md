# Yandex Wordstat MCP (Cursor)

**Дата:** 2026-08-13  
**Назначение:** частоты / похожие / динамика / регионы Wordstat v2 из чата Cursor.

## Что подключено

- Пакет: [`yandex-wordstat-mcp`](https://www.npmjs.com/package/yandex-wordstat-mcp) (Search API v2)
- Лаунчер: `scripts/mcp-yandex-wordstat.ps1`
- Секреты: `secrets/wordstat.env` (в `.gitignore`)
- Конфиг Cursor: `%USERPROFILE%\.cursor\mcp.json` → сервер `yandex-wordstat`

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

1. Cursor → Settings → MCP → перезапустить `yandex-wordstat` (или Reload Window).
2. Проверка в чате: «Покажи топ Wordstat по „проверка стажа“».

## Billing

Запросы Wordstat v2 тарифицируются через Yandex Cloud Search API. Смотреть квоты в консоли каталога.

## Не делать

- Не коммитить `secrets/wordstat.env` и API-ключи.
- Не класть ключи в git-tracked `.cursor/` проекта.
