# Яндекс Бизнес — сбор и ответы на отзывы

**Профиль:** `234170727274`  
**Форма отзыва:** https://yandex.ru/sprav/234170727274/reviews/add/  
**ТЗ:** [19-yandex-reviews-feedback.md](../specs/19-yandex-reviews-feedback.md)  
**Статья Яндекса:** https://direct.yandex.ru/base/articles/kak-pravilno-motivirovat-klientov-ostavlyat-otzyvy  
**Промоматериалы в кабинете:** https://yandex.ru/sprav/234170727274/p/edit/promo/

---

## Готовые файлы в репо

| Файл | Назначение |
|------|------------|
| `scripts/assets/yandex-business/promo/qr-review.png` | QR на форму |
| `scripts/assets/yandex-business/promo/card.pdf` | Визитка |
| `scripts/assets/yandex-business/promo/booklet.pdf` | Буклет |
| `assets/qr.png` | тот же QR (исправлен) |
| `assets/card.pdf` / `assets/booklet.pdf` | исходники из кабинета |

Публичный QR на сайте (после деплоя):  
`https://proverkastaza.ru/yandex-review-qr.png`

---

## Как просить (не навязчиво)

1. Только после спокойного завершения услуги.
2. Одна короткая просьба в MAX (вариант A или B в `review-request-templates.md`).
3. По желанию приложить `qr-review.png`.
4. Напоминание — **не раньше 3 дней**, не чаще одного раза, только если уместно.
5. При отказе или молчании после напоминания — **стоп**.

Нельзя: бонусы за отзыв, «поставьте 5», просьбы «своим», давление звонками.

---

## Ответы на отзывы

Шаблоны: `scripts/assets/yandex-business/review-reply-templates.md`.  
Проверять кабинет Пн/Чт, отвечать за 1–2 рабочих дня.

---

## Журнал

`review-requests-log.example.csv` — без ФИО, только `case_id` и статусы `asked` / `reminded` / `declined` / `done`.
