# Плагины Яндекс Трекера (Weavix)

Локальные Tracker-плагины для организации SFRFR. **Не деплоятся на VPS** — только код в репозитории и отладка через `weavix debug`.

## Плагины

| Каталог | Plugin ID | Слот | Назначение |
|---------|-----------|------|------------|
| [sfrfr-issue-wizard](./sfrfr-issue-wizard/) | `sfrfr-issue-wizard` | `navigation` | Мастер задач STAZH / SFRFR / PUB / FUNNEL |

Подробнее: [docs/TRACKER/plugin-sfrfr-issue-wizard.md](../../docs/TRACKER/plugin-sfrfr-issue-wizard.md).

## Быстрый старт (debug)

```powershell
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix debug
```

1. Дождаться URL/порта в консоли (обычно Vite на `http://localhost:5173`).
2. В Трекере: **Настройки → Эксперименты → Отладка плагинов** — подключить локальный плагин.
3. Открыть слот **navigation** (боковое меню / навигация).

Если `weavix debug` просит `weavix login` / OAuth — выполнить login один раз (токен не коммитить).

## Важно

- Не коммитить `node_modules/`, секреты, OAuth-токены.
- Пуш только `plugins/tracker/**` не должен запускать `deploy-vps` (`paths-ignore`).
