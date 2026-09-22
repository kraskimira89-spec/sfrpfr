# 2026-09-22 — ads → канал: PR, главная, UTM, закреп

## Сделано в коде

- Главная: primary «Подписаться на канал MAX» (hero + блок связи).
- `wp_apply_home.php`: UTM `max_channel_subscribe` для `home_hero` / `home_max_guide`.
- Закреп `00-pinned`: кнопка «Подать заявку».
- Брифы Директ / UTM playbook.

## Владелец (реклама вне репо)

Перевести destination активных объявлений на:

```text
https://max.ru/channel_proverkastaza?utm_source=<src>&utm_medium=<med>&utm_campaign=max_channel_subscribe&utm_content=<place>
```

Не вести холодный трафик на `id8905998693_1_bot`.

После merge + deploy: seed home на VPS; `sfrfr max-channel-publish-starter --only 00-pinned`.
