# Посты канала MAX «Проверка стажа»

Канал: https://max.ru/channel_proverkastaza  
ТЗ: `docs/specs/23-max-channel-promotion.md`  
Ops: `docs/ops/max-channel-chat-id.md`

## Путь публикации

```text
черновик в starter-posts.json
  → ручная вычитка
  → sfrfr max-channel-publish-starter
  → проверка в канале
```

## Команды

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr max-channel-publish-starter --dry-run
sfrfr max-channel-publish-starter
```

Первый пост (`pin: true`) закрепляется через `PUT /chats/{id}/pin`.

Не коммитить ПДн, обещания перерасчёта и непроверенные ссылки.
