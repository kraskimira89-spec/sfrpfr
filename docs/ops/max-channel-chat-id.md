# Ops: получить `chat_id` канала MAX

**Канал:** https://max.ru/channel_proverkastaza  
**ТЗ:** [ТЗ-23](../specs/23-max-channel-promotion.md)

С июня 2026 `GET /chats` не поддерживается. ID канала берём из webhook-события `bot_added` (или сообщения в канале).

## 1. Подписать webhook (с `bot_added`)

На машине с `.env` (токен и `PUBLIC_BASE_URL`):

```powershell
.\.venv\Scripts\Activate.ps1
sfrfr max-subscribe
```

В подписку входят: `message_created`, `bot_started`, `bot_added`, `bot_removed`, `message_callback`.

Webhook: `{PUBLIC_BASE_URL}/api/integrations/max/webhook`.

## 2. Добавить бота админом канала

1. Открыть канал.
2. Добавить того же бота, что ведёт личный чат.
3. Право: публиковать посты / администратор.

Если бот уже был добавлен до обновления подписки — **удалите и добавьте снова**, чтобы пришло `bot_added`.

## 3. Найти `chat_id`

### На VPS (логи)

Ищите строку:

```text
max_channel_chat_id_seen chat_id=... → set MAX_CHANNEL_CHAT_ID=...
```

или `action=bot_added` / `max_bot_added`.

### Локально / после деплоя

Важно: `sfrfr max-subscribe` указывает webhook на **VPS** (`PUBLIC_BASE_URL`).  
События `bot_added` пишутся в `var/max_channel_ids.json` **на сервере**, не на вашем ПК.

```powershell
sfrfr max-channel-info
# по умолчанию --remote: читает GET /api/integrations/max/channel-ids на VPS
```

Смотрите поле `remote_discovered`.  
`local_discovered` на ноутбуке обычно пуст — это нормально.

## 4. Записать в secrets

```env
MAX_CHANNEL_URL=https://max.ru/channel_proverkastaza
MAX_CHANNEL_CHAT_ID=<число_из_лога>
```

На VPS — в production `.env`, затем перезапуск API.

## 5. Тест публикации

```powershell
sfrfr max-channel-post -t "Тест: публикация через API SFRFR"
```

В канале должен появиться пост. Текст без ПДн и без обещаний перерасчёта.

## 6. Боевой путь

```text
черновик → ручная проверка → sfrfr max-channel-post / API → проверка в канале
```

Long poll (`scripts/max_listen_chat_id.py`) при активном webhook обычно пуст — для канала не использовать.
