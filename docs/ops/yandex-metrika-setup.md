# Яндекс Метрика для SFRFR (вариант B: API + код на WP)

**Сайт:** `https://proverkastaza.ru`  
**Счётчик:** `111134477`  
**Правило ПДн:** в цели/URL/params — только технические коды, без телефонов/ФИО/email.

Отдельно от Workspace OAuth и Cloud AI.

---

## Согласие (P0)

MU-plugin **не** грузит `mc.yandex.ru` до выбора «Разрешить».  
Отказ сохраняется в `localStorage` (`sfrfr_metrika_consent:metrika-consent-2026-07-29`).  
Вебвизор выключен (`YANDEX_METRIKA_WEBVISOR=0`).

---

## OAuth

1. [oauth.yandex.ru](https://oauth.yandex.ru/) → приложение **SFRFR Metrika**.
2. Redirect URI: `https://oauth.yandex.ru/verification_code`.
3. Права: `metrika:read`, `metrika:write`.
4. Токен: `https://oauth.yandex.ru/authorize?response_type=token&client_id=CLIENT_ID` → `access_token=y0_…`.

Секреты: `secrets/yandex-metrika.env` (см. `docs/ops/yandex-metrika.env.example`).

```env
YANDEX_METRIKA_EXCLUDE_IPS=1.2.3.4,5.6.7.8
YANDEX_METRIKA_EXCLUDE_MY_IP=1
```

---

## Ensure (API)

```powershell
python scripts/yandex_metrika_ensure_counter.py
```

Скрипт:

1. Находит/создаёт счётчик `proverkastaza.ru`.
2. `filter_robots=1`.
3. JS-цели: `lead_ok`, `max_click`, `lead_start`, `cabinet_click`, `tariff_view`, `form_error`.
4. Фильтры exclude по IP команды (`EXCLUDE_IPS` + опционально IP запуска).
5. Операции `cut_parameter` для email/phone/fio/snils/token и т.п.

---

## Деплой на WP

```bash
sudo bash /opt/sfrfr/scripts/wp_deploy_metrika.sh
# при обновлении текста cookies:
sudo php /opt/sfrfr/scripts/wp_upsert_legal_pages.php
```

MU: `scripts/wp-mu-plugins/sfrfr-yandex-metrika.php`

---

## Цели на витрине

| Код | Триггер |
|-----|---------|
| `max_click` | клик по ссылке MAX |
| `cabinet_click` | клик на cabinet.proverkastaza.ru |
| `lead_start` | `#zayavka` или первый focus в форме |
| `tariff_view` | секция `#tarify` в viewport |
| `lead_ok` | WPForms success |
| `form_error` | WPForms error |

---

## Проверка

1. Инкогнито без блокировщика: баннер → без «Разрешить» нет `mc.yandex.ru`.
2. «Разрешить» → Network: `tag.js` / `watch`.
3. MAX → `max_click`; заявка → `lead_ok`.
4. Метрика → «Онлайн» / отчёт по целям.

---

## Пока не включать

- Вебвизор — до маскирования полей формы.
- CRM / offline-конверсии.
- Сырые логи Метрики в BI (в DataLens — только агрегаты).
