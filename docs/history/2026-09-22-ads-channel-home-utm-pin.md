# 2026-09-22 — ads → канал: PR, главная, UTM, закрепы

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

## После deploy

- Seed home: `vps_deploy.sh` → `wp_apply_landing_vps.sh` (проверено live: primary CTA → канал + UTM `home_hero` / `home_max_guide`).
- Закреп republish: `sfrfr max-channel-publish-starter --direct --only 00-pinned` → mid `mid.ffffb970e931d56801a0c80b806c4afe`, pin `success`, пост https://max.ru/channel_proverkastaza/AaDIC4BsSv4 (кнопка «Подать заявку» → `MAX_CHAT_URL`).
