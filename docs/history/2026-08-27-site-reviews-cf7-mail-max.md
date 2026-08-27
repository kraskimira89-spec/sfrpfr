# 2026-08-27 — отзывы на сайте: CF7 + почта + MAX + модерация

## Было

- `/otzyvy/`: самописная HTML/JS-форма → `POST /api/public/site-reviews` → `pending` в `var/site_reviews.json`.
- Без письма на `proverkastaza@yandex.ru` и без уведомления в MAX.
- Рейтинг: Яндекс Карты (`/otzyv/`); анкета: Яндекс Форма.

## Стало

- CF7 «Отзыв на сайте» → mail `proverkastaza@yandex.ru` + Flamingo.
- MU `sfrfr-cf7-site-review.php` после `mail_sent` → API очередь + `_fanout_ops_text` (канал команды).
- Публикация только через `sfrfr site-reviews-set … --status published`.

## Файлы

- `scripts/wp_ensure_cf7_site_review.php` / `.sh`
- `scripts/wp-mu-plugins/sfrfr-cf7-site-review.php`
- `scripts/assets/trust/otzyvy.html`
- `src/sfrfr/api/routes/public_site_reviews.py`
- `docs/marketing-sales/playbook-site-reviews-moderation.md`
