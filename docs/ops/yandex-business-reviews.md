# Яндекс Бизнес — сбор и ответы на отзывы

**Профиль:** `82469923047`  
**Карточка на Картах:** https://yandex.ru/maps/org/proverka_stazha/82469923047/  
**Форма отзыва:** https://yandex.ru/maps/org/proverka_stazha/82469923047/reviews/?add-review=true  
**Короткая ссылка:** https://proverkastaza.ru/otzyv/  
**ТЗ:** [19-yandex-reviews-feedback.md](../specs/19-yandex-reviews-feedback.md)  
**Статья Яндекса:** https://direct.yandex.ru/base/articles/kak-pravilno-motivirovat-klientov-ostavlyat-otzyvy  
**Промоматериалы в кабинете:** https://yandex.ru/sprav/82469923047/p/edit/promo/

Профиль и прайс: [yandex-business-profile.md](yandex-business-profile.md).

---

## Готовые файлы в репо

| Файл | Назначение |
|------|------------|
| `scripts/assets/yandex-business/promo/qr-review.png` | QR на форму |
| `scripts/assets/yandex-business/promo/card.pdf` | Визитка (пересобрать в кабинете после смены ID) |
| `scripts/assets/yandex-business/promo/booklet.pdf` | Буклет (то же) |
| `assets/qr.png` | тот же QR |
| `assets/card.pdf` / `assets/booklet.pdf` | исходники из кабинета |

Публичный QR на сайте (после деплоя):  
`https://proverkastaza.ru/yandex-review-qr.png`

Бейдж рейтинга (официальный виджет Sprav): на `/kontakty/` и в футере сайта.

```html
<iframe src="https://yandex.ru/sprav/widget/rating-badge/82469923047?type=rating" width="150" height="50" frameborder="0"></iframe>
```

Печатные материалы: `docs/brand/card.pdf`, `docs/brand/booklet.pdf` → копии в `scripts/assets/yandex-business/promo/`.


---

## Как просить (не навязчиво)

1. Авто: при `completed` — одно мягкое сообщение в MAX (без серии повторов).
2. Вручную при необходимости: шаблон A/B в `review-request-templates.md`.
3. По желанию приложить `qr-review.png`.
4. Ручное напоминание — **не раньше 3 дней**, не чаще одного раза, только если уместно.
5. При отказе или молчании после напоминания — **стоп**.

Нельзя: бонусы за отзыв, «поставьте 5», просьбы «своим», давление звонками, авто-серия напоминаний.

---

## Ответы на отзывы

Шаблоны: `scripts/assets/yandex-business/review-reply-templates.md`.  
Проверять кабинет **ежедневно** (чек-лист Яндекса); отвечать за 1–2 рабочих дня.  
Структура негатива и границы SFRFR: [playbook-yandex-business-card.md](../marketing-sales/playbook-yandex-business-card.md).

---

## Журнал

`review-requests-log.example.csv` — без ФИО, только `case_id` и статусы `asked` / `reminded` / `declined` / `done`.
