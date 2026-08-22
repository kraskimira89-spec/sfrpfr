# Посты канала MAX «Проверка стажа»

Канал: https://max.ru/channel_proverkastaza  
ТЗ: `docs/specs/23-max-channel-promotion.md`  
Ops: `docs/ops/max-channel-chat-id.md`  
Сегмент (Launchi): `docs/marketing-sales/research-launchi-max-1000-subscribers.md`

## Файлы

| Файл | Назначение |
|------|------------|
| `starter-posts.json` | Закреп + стартер + план 07–18 (публиковать только с `--only`) |
| `daily-queue.json` | Очередь ежедневного полуавто (`max-channel-daily-tick`) |
| `plan-2026-08-17.json` | Копия постов плана (с блоком про кнопку) |
| `channel-description.md` | Текст описания канала для ручной вставки в UI MAX |

## Путь публикации

```text
черновик в starter-posts.json
  → ручная вычитка
  → sfrfr max-channel-publish-starter [--only 00-pinned]
  → проверка в канале
```

Только закреп-представление:

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr max-channel-publish-starter --only 00-pinned
```

Ежедневный полуавто (один пост → ops):

```powershell
sfrfr max-channel-daily-tick --dry-run
sfrfr max-channel-daily-tick
```

Описание канала (`channel-description.md`) публикуется **только вручную** в настройках MAX.

Ops cron: `docs/ops/max-channel-daily-cron.md`.
Playbook (ежедневно): `docs/marketing-sales/playbook-max-channel-month-2026-08.md`.
Чтобы выпустить один пост вручную: `--only 09-sverka`. Без `--only` стартовый файл не гонять.
