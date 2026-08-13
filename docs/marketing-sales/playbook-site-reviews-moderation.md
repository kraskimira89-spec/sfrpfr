# Очередь цитат для главной (модерация)

**Дата:** 2026-08-13  
**Канон:** рейтинг только Яндекс; цитаты на сайте — после модерации.

## Файлы / API

| Что | Где |
|-----|-----|
| Хранилище | `var/site_reviews.json` на API-хосте |
| Публичный список | `GET /api/public/site-reviews` |
| Постановка в очередь | чекбокс в `/anketa-otzyv/` → `POST /api/public/review-draft` (`site_quote_consent`) |
| CLI | `sfrfr site-reviews-list` / `sfrfr site-reviews-set` |

## Команды

```bash
# На VPS в /opt/sfrfr
.venv/bin/sfrfr site-reviews-list --status pending
.venv/bin/sfrfr site-reviews-set <uuid> --status published
.venv/bin/sfrfr site-reviews-set <uuid> --status rejected
```

## Правила модерации

- Без ФИО, СНИЛС, сумм пенсии, номеров дел.
- Без «поставьте 5» и обещаний перерасчёта.
- Короткий текст о сервисе (ясность, сроки, удобство).
- Не публиковать «всё подряд»: только `published` попадают на главную.

## Главная

Блок `#otzyvy`: бейдж Sprav + `/otzyv/` + цитаты из API.
