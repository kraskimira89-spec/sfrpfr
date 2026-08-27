# 2026-08-27 — UX /otzyvy/ для 55+

## Зачем

Три равноправных действия на первом экране путали. Ошибка CF7 + короткие тексты ломали доверие.

## Что сделано

- Два главных способа: Яндекс Карты + короткая анкета; форма сайта в disclosure.
- Отдельное согласие на публикацию; без него статус `feedback`.
- CF7: `your-useful` / `your-improve`, понятные сообщения, валидация `textarea*`.
- Аналитика целей без ПДн.
- Блок «Как мы публикуем отзывы», пока нет цитат.

## Файлы

- `scripts/assets/trust/otzyvy.html`
- `scripts/assets/sfrfr-landing.css`
- `scripts/wp_ensure_cf7_site_review.php`
- `scripts/wp-mu-plugins/sfrfr-cf7-site-review.php`
- `scripts/wp-mu-plugins/sfrfr-seo-meta.php`
- `src/sfrfr/core/site_reviews.py`
- `src/sfrfr/api/routes/public_site_reviews.py`
- `docs/marketing-sales/playbook-site-reviews-moderation.md`
