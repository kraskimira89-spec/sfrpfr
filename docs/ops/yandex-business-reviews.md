# Яндекс Бизнес — сбор и ответы на отзывы

**Профиль:** `234170727274`  
**ТЗ:** [19-yandex-reviews-feedback.md](../specs/19-yandex-reviews-feedback.md)  
**Статья Яндекса:** https://direct.yandex.ru/base/articles/kak-pravilno-motivirovat-klientov-ostavlyat-otzyvy  
**Справка по отзывам:** https://yandex.ru/support/business-priority/ru/manage/reviews  
**Промоматериалы:** https://yandex.ru/support/business-priority/ru/manage/promo

---

## P0 — один раз в кабинете (нужен браузер / CAPTCHA)

1. Открыть https://yandex.ru/sprav/234170727274/
2. **О компании → Отзывы** → получить / скопировать **ссылку на форму отзыва**.
3. **О компании → Промоматериалы** → скачать QR-код (PNG) и при желании визитку/пирамидку.
4. Сохранить URL локально:

```text
secrets/yandex-business-review.env
YANDEX_BUSINESS_REVIEW_URL=https://yandex.ru/maps/org/.../reviews/?add-review=true
```

Шаблон: `scripts/assets/yandex-business/review-url.env.example`.

5. Подставить URL в сообщения из `scripts/assets/yandex-business/review-request-templates.md`.

---

## Еженедельный ритм

| День | Действие |
|------|----------|
| После завершения услуги | Первая просьба в MAX |
| +1…3 дня | Одно напоминание, если нет отзыва и нет отказа |
| Пн / Чт | Проверить новые отзывы в Sprav, ответить по шаблонам |
| Раз в месяц | Сверить число просьб vs опубликованных отзывов (без ПДн) |

---

## Запрещено (Яндекс + SFRFR)

- платить за отзыв / дарить бонус за текст или скрин;
- просить сотрудников, друзей, родственников;
- давить повторными звонками;
- просить описать «повышение пенсии» как факт услуги;
- публиковать AggregateRating / «накрученный» рейтинг на сайте.

---

## Файлы

| Файл | Назначение |
|------|------------|
| `scripts/assets/yandex-business/review-request-templates.md` | MAX: просьба, напоминание, вопросы |
| `scripts/assets/yandex-business/review-reply-templates.md` | Ответы компании в Картах |
| `scripts/assets/yandex-business/review-requests-log.example.csv` | Журнал без ФИО |
| `docs/ops/yandex-business-profile.md` | Карточка и прайс |

---

## Ответ на отзыв

- тон спокойный, благодарность, без спора «вы неправы»;
- не раскрывать детали дела;
- при ошибке сервиса — извинение + канал MAX для разбора;
- при путанице с ролью СФР — коротко напомнить: решение принимает СФР, мы — сопровождение документов.
