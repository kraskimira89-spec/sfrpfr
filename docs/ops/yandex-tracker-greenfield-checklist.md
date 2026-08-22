# Чеклист: Трекер с нуля (greenfield, без Notion)

**Дата:** 2026-08-22  
Notion **не** переносим — только новый контур.

## Подготовка

- [ ] `.\scripts\bootstrap_yandex_tracker_mcp.ps1` (клон aikts + pip install)
- [ ] OAuth **Tracker** (не Workspace) + org id → `secrets/yandex-tracker.env`
- [ ] В `%USERPROFILE%\.cursor\mcp.json` — command на `scripts/mcp-yandex-tracker.cmd`
- [ ] Cursor MCP Reload → `yandex-tracker` Connected

## Трекер (UI)

- [ ] Очередь **`SFRFR`** создана
- [ ] Доска **SFRFR** (Open / In Progress / Done)
- [ ] Типы **Task**, **Bug** (и при необходимости Story)
- [ ] Smoke-задача из Cursor: «Создай задачу SFRFR: smoke MCP» — видна в UI

## Wiki

- [ ] Раздел **SFRFR** в Яндекс Wiki (оглавление, без импорта Notion)
- [ ] Ссылки на ключевые `docs/` репо (marketing-sales, ops, AMO)

## amoCRM

- [ ] Новые CRM-заметки — только в amo ([`docs/AMO/`](../AMO/README.md))
- [ ] В Трекер/Wiki нет ФИО/телефонов клиентов

## Notion off

- [ ] Plugin `notion-workspace` disabled в [`.cursor/settings.json`](../../.cursor/settings.json)
- [ ] Notion MCP не в `mcp.json`

## Документация в репо

- [ ] SoT инструментов отражён в [`docs/marketing-sales/README.md`](../marketing-sales/README.md)

## Критерий «готово»

Задачи ведутся в Трекере; Cursor создаёт issues через MCP; wiki/ТЗ — Wiki + git; CRM — amo; Notion вне процесса.
