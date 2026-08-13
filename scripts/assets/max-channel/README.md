# Посты канала MAX «Проверка стажа»

Канал: https://max.ru/channel_proverkastaza  
ТЗ: `docs/specs/23-max-channel-promotion.md`  
Ops: `docs/ops/max-channel-chat-id.md`  
Сегмент (Launchi): `docs/marketing-sales/research-launchi-max-1000-subscribers.md`

## Файлы

| Файл | Назначение |
|------|------------|
| `starter-posts.json` | Закреп + 5 постов (коллеги → чек-лист → снижение → границы → MAX) |
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

Описание канала (`channel-description.md`) публикуется **только вручную** в настройках MAX.

## Команды

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr max-channel-publish-starter --dry-run
sfrfr max-channel-publish-starter
```

Первый пост (`pin: true`) закрепляется через `PUT /chats/{id}/pin`.

Не коммитить ПДн, обещания перерасчёта и непроверенные ссылки.
