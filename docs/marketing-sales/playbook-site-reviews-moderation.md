# Очередь цитат / сообщений для /otzyvy/ и главной

**Дата:** 2026-08-13  
**Канон:** рейтинг только Яндекс Карты.

## UX на https://proverkastaza.ru/otzyvy/

1. **Яндекс Карты** — бейдж + «Оставить отзыв» → `/otzyv/`.  
2. **Анкета** — встроенная [Яндекс Форма](https://forms.yandex.ru/cloud/6a7db97670ad3712589c7456/) (подсказки к тексту).  
3. **Сообщение нам** — простая форма внизу → очередь модерации (`pending`).  

ИИ-черновик на этой странице не используем.

## Модерация

```bash
.venv/bin/sfrfr site-reviews-list --status pending
.venv/bin/sfrfr site-reviews-set <uuid> --status published
.venv/bin/sfrfr site-reviews-set <uuid> --status rejected
```

На витрину и главную попадают только `published`.
