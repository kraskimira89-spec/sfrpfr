# Плагины Яндекс Трекера (Weavix)

Локальные Tracker-плагины для организации SFRFR. **Не деплоятся на VPS** — только код в репозитории и отладка через `weavix debug`.

## Плагины

| Каталог | Plugin ID | Слот | Порт debug | Назначение |
|---------|-----------|------|------------|------------|
| [sfrfr-issue-wizard](./sfrfr-issue-wizard/) | `sfrfr-issue-wizard` | `navigation` | 5173 | Мастер SFRFR / PUB / FUNNEL (ассеты marketplace готовы к `weavix submit`) |
| [stazh-quality-wizard](./stazh-quality-wizard/) | `stazh-quality-wizard` (`654059d7-…`, v0.1.1 **IN_REVIEW**) | `navigation` | 5174 | Качество / улучшения → **STAZH** (без ПДн) |

Документация:

- [docs/TRACKER/plugin-sfrfr-issue-wizard.md](../../docs/TRACKER/plugin-sfrfr-issue-wizard.md)
- [docs/TRACKER/plugin-stazh-quality-wizard.md](../../docs/TRACKER/plugin-stazh-quality-wizard.md)
- Ops MVP кабинет → STAZH: [docs/ops/yandex-tracker-stazh-quality.md](../../docs/ops/yandex-tracker-stazh-quality.md)

## Быстрый старт (debug)

```powershell
# Продукт / публикации / воронка
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix debug

# Качество STAZH (другой порт)
cd plugins\tracker\stazh-quality-wizard
npm install
weavix debug
```

1. Дождаться старта Vite (`5173` или `5174`, в `config.json` будет `downloadUrl`).
2. В Трекере: **Настройки → Эксперименты → Отладка плагинов** — подключить локальный плагин.
3. Открыть слот **navigation**.

⚠️ Не открывайте localhost в браузере — плагин грузится только из интерфейса Трекера.

Если CLI просит согласие с условиями — один раз `y`. Для publish/submit: `weavix login` (токен не коммитить).

## Важно

- Не коммитить `node_modules/`, `config.json` (генерирует debug), `.yaweavix-debug.lock`, секреты, OAuth-токены.
- Пуш только `plugins/tracker/**` не должен запускать `deploy-vps` (`paths-ignore`).
