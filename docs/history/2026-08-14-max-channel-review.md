# 2026-08-14 — премодерация постов MAX

## Зачем
Перед публикацией в клиентский канал черновик уходит в канал специалистов с кнопками «Опубликовать» / «Редактировать» (clipboard + правка сообщением).

## Что сделано
- `channel_drafts.py` — store `storage/max_channel_drafts.json`, payload `chdraft:*`, клавиатура review
- `channel_review.py` — отправка в канал команды (ops) и публикация клиентским ботом
- `ops_bot.py` — callback pub/edit + ожидание правки
- CLI: `max-channel-review`, `max-channel-post --review`, `max-channel-publish-starter` по умолчанию `--review` (`--direct` — сразу клиентам)
- Docs: `docs/ops/max-channel-review.md`, playbook месяца, gitignore drafts

## Как пользоваться
```powershell
sfrfr max-channel-publish-starter --only <id>
# в канале команды: Опубликовать → клиентский канал
```
