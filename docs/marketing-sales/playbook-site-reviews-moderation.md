# Очередь цитат / отзывов для /otzyvy/ и главной

**Дата:** 2026-08-13  
**Канон:** рейтинг только Яндекс Карты.

## UX на https://proverkastaza.ru/otzyvy/

1. **Яндекс Карты** — бейдж + «Оставить отзыв на Картах» → `/otzyv/`.  
2. **Анкета** — кратко, зачем форма (вопросы о сервисе, ФИО и контакт) + кнопка **Яндекс Форма** → https://forms.yandex.ru/cloud/6a7db97670ad3712589c7456/  
3. **Оставить отзыв на сайте** — компактная форма над цитатами (текст | капча + согласие + кнопка) → очередь модерации (`pending`). Согласие: ссылка на `/soglasie/`. Почту и телефон не спрашиваем.

## Модерация

```bash
.venv/bin/sfrfr site-reviews-list --status pending
.venv/bin/sfrfr site-reviews-set <uuid> --status published
.venv/bin/sfrfr site-reviews-set <uuid> --status rejected
```

На витрину и главную попадают только `published`.
