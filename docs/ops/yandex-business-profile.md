# Яндекс Бизнес — карточка ООО «ПОД ПРИСМОТРОМ»

**Профиль Sprav:** `234170727274`  
**Кабинет прайса:** https://yandex.ru/sprav/234170727274/p/edit/price-lists/  
**Сайт:** https://proverkastaza.ru (без www)  
**ТЗ-18:** достоверный профиль в каталогах, без ложных обещаний.

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
| Email | prismotr89@yandex.ru |
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

## Прайс (3 услуги = сайт)

| ID | Название | Цена | URL |
|----|----------|------|-----|
| `diag-3000` | Диагностика проверки стажа | 3000 ₽ | `/tarify/` |
| `support-10000` | Сопровождение по документам и этапам | 10000 ₽ | `/tarify/` |
| `turnkey-25000` | Комплекс «Под ключ» | 25000 ₽ | `/proverka-stazha/` |

Файлы в репо:

- `scripts/assets/yandex-business/price-list.yml`
- `scripts/assets/yandex-business/price-list.xlsx` (собрать: `python scripts/build_yandex_business_price_xlsx.py`)

Публичный YML-фид:

```text
https://proverkastaza.ru/yandex-business-price.yml
```

---

## Как загрузить в кабинет

1. Войти в https://yandex.ru/sprav/234170727274/p/edit/price-lists/ (пройти CAPTCHA).
2. **Вариант A:** О компании → Товары и услуги → Загрузить XLS/YML → файл `price-list.xlsx`.
3. **Вариант B:** источник «YML-фид» → URL `https://proverkastaza.ru/yandex-business-price.yml`.
4. Дождаться модерации (в Картах до суток). Новый файл **заменяет** старый прайс целиком.

Перевыкладка фида на VPS после правок:

```bash
scp scripts/assets/yandex-business/price-list.yml root@VPS:/var/www/taxi-doroga-dobra/yandex-business-price.yml
# или: bash scripts/wp_deploy_yandex_business_price.sh
```

---

## Связь с SEO

- ТЗ-18: профиль в Яндекс Бизнесе как сигнал доверия.
- Вебмастер: смотреть хост **без www** (`docs/ops/yandex-webmaster-setup.md`).
