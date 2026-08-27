# Очередь цитат / отзывов для /otzyvy/ и главной

**Дата:** 2026-08-27  
**Канон:** рейтинг только Яндекс Карты; цитаты на сайте — только после модерации.

## UX на https://proverkastaza.ru/otzyvy/

1. **Яндекс Карты** — бейдж + QR (`/yandex-review-qr.png` → `/otzyv/`) + «Оставить отзыв на Картах».  
2. **Анкета** — Яндекс Форма → https://forms.yandex.ru/cloud/6a7db97670ad3712589c7456/  
3. **Оставить отзыв на сайте** — **Contact Form 7** «Отзыв на сайте» (маркер `<!-- SFRFR_SITE_REVIEW_FORM -->`):
   - письмо на `proverkastaza@yandex.ru` + копия во **Flamingo**;
   - после `mail_sent` MU шлёт в API очередь `pending` и fanout в **MAX** (канал команды / менеджеры);
   - на витрину и главную — только после approve.

## Доставка

| Канал | Куда |
|---|---|
| Почта | `proverkastaza@yandex.ru` — кликабельные ссылки «Одобрить» / «Отклонить» |
| Flamingo | WordPress → **Контакт → Входящие** |
| MAX | кнопки **Одобрить** / **Отклонить** в ops-боте (`srev:p:` / `srev:r:`) |

## Модерация (публикация на сайте)

В MAX — нажать кнопку. В письме — открыть ссылку. CLI:

```bash
.\.venv\Scripts\Activate.ps1
sfrfr site-reviews-list --status pending
sfrfr site-reviews-set <uuid> --status published
sfrfr site-reviews-set <uuid> --status rejected
```

На витрину и главную попадают только `published`. Рейтинг Яндекса форма не меняет.

## Деплой / ensure

```bash
SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_ensure_cf7_site_review.sh
SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_trust_pages_tz18.sh
```

Форму CF7 перезаписывает `wp_ensure_cf7_site_review.php` — поля править в репозитории, не в UI.

## Чеклист WP admin (если письмо не приходит)

1. Плагины **Contact Form 7** и **Flamingo** активны.  
2. Форма «Отзыв на сайте» существует (ensure-скрипт), id в `sfrfr_cf7_site_review_id`.  
3. В форме Mail → To: `proverkastaza@yandex.ru`, Mail active.  
4. Тест: отправить форму → **письмо** + запись в **Flamingo** (`Контакт → Входящие`).  
5. На VPS в `/opt/sfrfr/.env`: `MAX_SPECIALISTS_CHANNEL_CHAT_ID`, токен ops-бота; `PUBLIC_LEAD_TOKEN` совпадает с WP (`sfrfr-lead.config.php` / env), иначе очередь/MAX с CF7 не доедут.

### Проверка 2026-08-27 / доработка

| Шаг | Результат |
|---|---|
| CF7 + Flamingo active | ок |
| Форма «Отзыв на сайте» | id `2984` |
| Flamingo inbound | ок |
| Письмо | **Яндекс SMTP**: MU `sfrfr-wp-mail-relay.php` → `/api/public/wp-mail-relay` (замена SMTP-плагина) |
| Fallback | при `mail_failed` — API всё равно ставит в очередь и шлёт уведомление |
| Модерация | MAX-кнопки + HTTPS-ссылки в письме (`/api/public/site-reviews/moderate`) |

На WP **не** ставим postfix/FluentSMTP: исходящая почта канона — Яндекс SMTP через API SFRFR.
