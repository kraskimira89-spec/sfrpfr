# Посты канала MAX «Проверка стажа»

Канал: https://max.ru/channel_proverkastaza  
ТЗ: `docs/specs/23-max-channel-promotion.md`  
Ops: `docs/ops/max-channel-chat-id.md`  
Сегмент (Launchi): `docs/marketing-sales/research-launchi-max-1000-subscribers.md`

## Файлы

| Файл | Назначение |
|------|------------|
| `starter-posts.json` | Закреп + стартер + план 07–18 (публиковать только с `--only`) |
| `plan-2026-08-17.json` | Копия постов плана 15.08–09.09 (с блоком про кнопку) |
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

Месячный план (календарь + тексты): `docs/marketing-sales/playbook-max-channel-month-2026-08.md`.
Чтобы выпустить один пост из плана, перенесите объект в `starter-posts.json` и вызовите `--only 07-no-calc` (и т.д.). Без `--only` стартовый файл не гонять.
