# Очередь цитат / отзывов для /otzyvy/ и главной

**Дата:** 2026-08-27  
**Канон:** рейтинг только Яндекс Карты; цитаты на сайте — только после **отдельного** согласия на публикацию и модерации.

## UX на https://proverkastaza.ru/otzyvy/

Линейный путь для 55+: **выберите один удобный способ**.

1. **Яндекс Карты** — публичный отзыв (кнопка основная; QR вторичный, на мобиле скрыт).  
2. **Короткая обратная связь** — Яндекс Форма (~1 мин). Контакты в копирайте — только по желанию.  
   Поля самой Яндекс Формы править в UI Яндекс Форм (не в репо).  
3. **Короткий отзыв на сайте** — в `<details>` («Хотите написать…»):
   - обязательное «Что было полезно?»;
   - необязательное «Что улучшить?»;
   - обязательное согласие на обработку текста;
   - необязательное согласие на публикацию на сайте без ПДн;
   - SmartCaptcha;
   - CF7 + Flamingo + API.

Без согласия на публикацию запись уходит как `feedback` (внутренняя ОС). С согласием — `pending` → approve → витрина.

## Доставка

| Канал | Куда |
|---|---|
| Почта | `proverkastaza@yandex.ru` — ссылки «Одобрить» / «Отклонить» только при `publish_consent` |
| Flamingo | WordPress → **Контакт → Входящие** |
| MAX | кнопки модерации только если автор разрешил публикацию |

## Модерация (публикация на сайте)

В MAX — нажать кнопку. В письме — открыть ссылку. CLI:

```bash
.\.venv\Scripts\Activate.ps1
sfrfr site-reviews-list --status pending
sfrfr site-reviews-set <uuid> --status published
sfrfr site-reviews-set <uuid> --status rejected
```

На витрину и главную — только `published`. Рейтинг Яндекса форма не меняет.

В MAX и письме сотруднику показывается **полный текст** отзыва (до 600 символов).
После нажатия кнопки / перехода по ссылке текст также виден в подтверждении.

## Аналитика (без ПДн и без текста отзыва)

`review_page_view`, `review_yandex_map_click`, `review_yandex_qr_view`, `review_survey_click`,  
`review_form_open`, `review_form_submit_attempt`, `review_form_submit_success`,  
`review_form_submit_error`, `review_publication_consent_checked`.

## Деплой / ensure

```bash
SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_ensure_cf7_site_review.sh
SITE_DIR=/var/www/taxi-doroga-dobra bash scripts/wp_seed_trust_pages_tz18.sh
```

Форму CF7 перезаписывает `wp_ensure_cf7_site_review.php` — поля править в репозитории.

## Чеклист WP admin

1. CF7 + Flamingo активны.  
2. Форма «Отзыв на сайте» (ensure), id в `sfrfr_cf7_site_review_id`.  
3. Mail → To: `proverkastaza@yandex.ru`.  
4. Тест: отправка → Flamingo + очередь API; письмо через MU `sfrfr-wp-mail-relay.php`.  
5. `PUBLIC_LEAD_TOKEN` совпадает у WP и API.

### Важно про SMTP

Текст отзыва в исходящем письме **маскируется** (`redact_outbound_body`: СНИЛС/паспорт → `[…]`). Шаблон CF7 mail body по-прежнему без слова «СНИЛС». Если пользователь копирует подсказку со страницы — CF7 и API вернут `hint_text` с понятным сообщением.

### Rollback

Вернуть предыдущие `scripts/assets/trust/otzyvy.html`, MU `sfrfr-cf7-site-review.php`, `wp_ensure_cf7_site_review.php`, CSS-блок `.sfrfr-otzyvy-*` и прогнать `wp_seed_trust_pages_tz18.sh` + `wp_ensure_cf7_site_review.sh`.
