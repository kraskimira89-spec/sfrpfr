# 2026-08-10 — Сид WP после копирайта «проект обращения»

## Что сделано на VPS
- `git reset --hard origin/main` в `/opt/sfrfr` (HEAD на момент сида)
- `wp_apply_landing_vps.sh` — главная, CSS, оферта, блог ТЗ-11
- `wp_seed_trust_pages_tz18.sh` — trust/тарифы/северный стаж и др.
- cache flush

## Проверка
Живые страницы: `/`, `/tarify/`, `/kak-rabotaem/`, `/proverka-severnogo-stazha/`.

## Повторный сид
После коммита `535a1dc` (канон снова в `tarify.html`, футере, MU blog/seo) —
повторный `git reset` + landing + trust + copy MU. На сайте: `проект обращения` + `расскажем по шагам`, старого «черновики и понятный план» нет.
