# 2026-08-12 — локальный Manrope без Google Fonts

## Запрос

Скачать шрифты и использовать без онлайн-обращения к Google Fonts.

## Сделано

- woff2 Manrope 400/500/600/700 (latin, latin-ext, cyrillic, cyrillic-ext) в `scripts/assets/fonts/manrope/`
- `@font-face` в `sfrfr-landing.css` → `/wp-content/uploads/sfrfr/fonts/manrope/`
- Копирование шрифтов в `wp_apply_landing_vps.sh` и `wp_seed_site_tz02.sh`
- Тест: нет `fonts.googleapis.com` в CSS

Кабинеты уже на `@fontsource/manrope`.

## После деплоя

```bash
bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
```
