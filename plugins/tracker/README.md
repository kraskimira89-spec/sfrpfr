# Плагины Яндекс Трекера (Weavix)

Локальные Tracker-плагины для организации SFRFR. **Не деплоятся на VPS** — только код в репозитории и отладка через `weavix debug`.

## Плагины

| Каталог | Plugin ID | Слот | Назначение |
|---------|-----------|------|------------|
| [sfrfr-issue-wizard](./sfrfr-issue-wizard/) | `sfrfr-issue-wizard` | `navigation` | Мастер создания задач SFRFR / PUB / FUNNEL |

Подробнее: [docs/TRACKER/plugin-sfrfr-issue-wizard.md](../../docs/TRACKER/plugin-sfrfr-issue-wizard.md).

## Быстрый старт (debug)

```powershell
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix debug
```

1. Дождаться старта (Vite обычно на `http://localhost:5173`, в `config.json` будет `downloadUrl`).
2. В Трекере: **Настройки → Эксперименты → Отладка плагинов** — подключить локальный плагин.
3. Открыть слот **navigation** (боковое меню / навигация).

⚠️ Не открывайте localhost в браузере — плагин грузится только из интерфейса Трекера.

Если CLI просит согласие с условиями — один раз `y`. Для publish/submit: `weavix login` (токен не коммитить).

## Важно

- Не коммитить `node_modules/`, `config.json` (генерирует debug), `.yaweavix-debug.lock`, секреты, OAuth-токены.
- Пуш только `plugins/tracker/**` не должен запускать `deploy-vps` (`paths-ignore`).
