# Очередь цитат для /otzyvy/ и главной (модерация)

**Дата:** 2026-08-13  
**Канон:** рейтинг только Яндекс; цитаты на сайте — после модерации.

## Файлы / API

| Что | Где |
|-----|-----|
| Хранилище | `var/site_reviews.json` на API-хосте |
| Публичный список | `GET /api/public/site-reviews` |
| Форма на `/otzyvy/` | `POST /api/public/site-reviews` (текст + согласие + капча) |
| Анкета | `/anketa-otzyv/` → `POST /api/public/review-draft` (`site_quote_consent`) |
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
- Не публиковать «всё подряд»: только `published` попадают на `/otzyvy/` и главную.

## Витрина

- `/otzyvy/`: форма + Яндекс + карточки `published`.
- Главная `#otzyvy`: бейдж + 2–3 цитаты + ссылка «Все отзывы».
- Анкета не дублируется кнопками на главной и контактах.
