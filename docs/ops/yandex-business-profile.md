# Яндекс Бизнес — карточка ООО «ПОД ПРИСМОТРОМ»

**Профиль Sprav:** `82469923047`  
**Кабинет прайса:** https://yandex.ru/sprav/82469923047/p/edit/price-lists/  
**Кабинет постов:** https://yandex.ru/sprav/82469923047/p/edit/posts/  
**Кабинет промо / отзывы:** https://yandex.ru/sprav/82469923047/p/edit/promo/  
**Форма отзыва:** https://yandex.ru/sprav/82469923047/reviews/add/  
**Карты:** https://yandex.ru/maps/org/proverka_stazha/82469923047/  
**Сайт:** https://proverkastaza.ru (без www)  
**ТЗ-18:** достоверный профиль в каталогах, без ложных обещаний.

Чек-лист оформления карточки (Яндекс PDF → адаптация SFRFR):  
[`docs/marketing-sales/playbook-yandex-business-card.md`](../marketing-sales/playbook-yandex-business-card.md)  
исходник: [`Инструкция_по_заполнению_карточки.pdf`](../marketing-sales/Инструкция_по_заполнению_карточки.pdf).

Дубликат `234170727274` удалён владельцем (2026-08-12). Все ссылки в репо ведут на `82469923047`. История сверки: `docs/history/2026-08-12-yandex-business-dual-cards.md`.

---

## Карточка организации (сверить в UI)

| Поле | Значение |
|------|----------|
| Бренд / витрина | Проверка стажа |
| Юр. лицо | ООО «ПОД ПРИСМОТРОМ» |
| ИНН | 8905066468 |
| КПП | 890501001 |
| ОГРН | 1208900000572 |
| Ген. директор | Лопакова Наталия Федоровна |
| Адрес | 629804, ЯНАО, г. Ноябрьск, ул. Рабочая, д. 109Б, кв. 4 |
| Телефон | +7 909 195-04-08 |
| Email | info@proverkastaza.ru |
| Сайт | https://proverkastaza.ru |
| Режим | Онлайн-консультации и подготовка документов, без визита в офис (по записи) |
| Услуга | https://proverkastaza.ru/proverka-stazha/ |
| Тарифы | https://proverkastaza.ru/tarify/ |
| Контакты | https://proverkastaza.ru/kontakty/ |
| Оферта | https://proverkastaza.ru/oferta/ |

Источник реквизитов: `docs/history/requisites-pod-prismotrom.md`.

### Не указывать

- гарантию перерасчёта / конкретную сумму выплат;
- статус государственного органа или «официальный СФР»;
- телефоны и ПДн в текстах позиций прайса (правила Яндекс Бизнеса).

---

## Прайс (4 позиции = сайт + YML)

**Статус:** репо и публичный фид совпадают (`date="2026-08-10 21:10"`). В Картах у `82469923047` видны все 4 позиции.

| ID | Название | Цена | URL |
|----|----------|------|-----|
| `diag-3000` | Диагностика проверки стажа | 3000 ₽ | `/tarify/` |
| `support-10000` | Сопровождение по документам и этапам | 10000 ₽ | `/tarify/` |
| `turnkey-25000` | Комплекс «Под ключ» | 25000 ₽ | `/proverka-stazha/` |
| `trudovaya-word-100` | Перенос трудовой в таблицу Word (за разворот) | 100 ₽ | `/tarify/` |

Файлы в репо:

- `scripts/assets/yandex-business/price-list.yml`
- `scripts/assets/yandex-business/price-list.xlsx` (собрать: `python scripts/build_yandex_business_price_xlsx.py`)

Публичный YML-фид:

```text
https://proverkastaza.ru/yandex-business-price.yml
```

Сверка: сайт `/tarify/` (3000 / 10000 / 25000 / 100 ₽ за разворот) = YML = карточка `82469923047`.

---

## Публикации (посты)

Готовые тексты со ссылками на сайт: `scripts/assets/yandex-business/posts.md` (8 постов).

1. Открыть https://yandex.ru/sprav/82469923047/p/edit/posts/ (CAPTCHA).
2. Создать публикацию → вставить текст из файла (ссылка только на `proverkastaza.ru`).
3. Модерация — до нескольких дней ([правила публикаций](https://yandex.ru/support/business-priority/ru/manage/publications)).

Рекомендуемый старт: посты 1–2 (услуга, тарифы), затем статьи блога.

События в Яндекс Календаре (`proverkastaza@yandex.ru`, среды 10:00 МСК с 05.08.2026):  
`python scripts/create_yandex_business_post_events.py` — в описании текст поста и ссылка на кабинет публикаций.

---

## Как загрузить прайс в кабинет

1. Войти в https://yandex.ru/sprav/82469923047/p/edit/price-lists/ (пройти CAPTCHA).
2. **Вариант A (рекомендуем):** О компании → Товары и услуги → **Загрузить XLS/YML** → вкладка **XLS** → файл `scripts/assets/yandex-business/price-list.xlsx`.
3. **Вариант B:** вкладка **YML** → файл `scripts/assets/yandex-business/price-list.yml` **или** источник «YML-фид» → URL `https://proverkastaza.ru/yandex-business-price.yml`.
4. Дождаться модерации (в Картах до суток). Новый файл **заменяет** старый прайс целиком.

Перевыкладка фида на VPS после правок:

```bash
scp scripts/assets/yandex-business/price-list.yml root@VPS:/var/www/taxi-doroga-dobra/yandex-business-price.yml
# или: bash scripts/wp_deploy_yandex_business_price.sh
```

---

## Отзывы (сбор обратной связи)

Полная инструкция: [yandex-business-reviews.md](yandex-business-reviews.md) · ТЗ-19.

1. Форма: https://yandex.ru/sprav/82469923047/reviews/add/ · QR/визитка/буклет в `scripts/assets/yandex-business/promo/` (исходники также в `docs/brand/`).
2. Бейдж рейтинга на сайте: iframe `https://yandex.ru/sprav/widget/rating-badge/82469923047?type=rating` — `/kontakty/` и футер.
3. Просьба только реальным клиентам, мягкие шаблоны: `review-request-templates.md`.
4. Без оплаты/бонуса; напоминание не раньше 3 дней и не чаще одного раза.
5. Ответы компании: `review-reply-templates.md`.

Кабинет промо: https://yandex.ru/sprav/82469923047/p/edit/promo/

---

## Связь с SEO

- ТЗ-18: профиль в Яндекс Бизнесе как сигнал доверия.
- ТЗ-19: легитимный сбор отзывов без накруток.
- Вебмастер: смотреть хост **без www** (`docs/ops/yandex-webmaster-setup.md`).
