# Яндекс Метрика для SFRFR (вариант B: API + код на WP)

**Сайт:** `https://proverkastaza.ru`  
**Счётчик:** `111134477`  
**Правило ПДн:** в цели/URL/params — только технические коды, без телефонов/ФИО/email.

Отдельно от Workspace OAuth и Cloud AI.

---

## Статус внедрения (чеклист)

| Раздел | Статус |
|--------|--------|
| OAuth `metrika:read/write` | ✅ |
| Счётчик Active + код на WP | ✅ |
| Согласие до `mc.yandex.ru` | ✅ статистические cookies, не СОПД |
| Внутренняя агрегация для всех | ✅ `sfrfr-internal-stats.php` |
| Цели P0 `lead_ok` / `max_click` | ✅ |
| Цели P1 воронки | ✅ |
| `filter_robots` + exclude IP + `cut_parameter` | ✅ |
| Reports API smoke | ✅ `scripts/yandex_metrika_report_smoke.py` |
| Вебвизор | ⏸ выкл. до маскирования полей |
| CRM / offline / Logs → BI | ⏸ не включать |

`code_status=CS_ERR_UNKNOWN` в API при отложенной загрузке после согласия — ожидаемо.

---

## Согласие (P0)

Баннер — согласие на **статистические файлы браузера** (Яндекс Метрика), **не** на СОПД заявки.

| Сценарий | Поведение |
|----------|-----------|
| До выбора | `mc.yandex.ru` не грузится |
| «Разрешить» | загружается Метрика; цели/клики/прокрутка |
| «Отказаться» | Метрика не грузится |

Параллельно для **всех** (включая отказ): собственная серверная агрегация без IP/ПДн — `sfrfr-internal-stats.php` (`page_view`, `lead_ok`, `form_error`, `http_404`, `consent_*`, `tech_error`).

Ключ: `sfrfr_metrika_consent:stat-cookies-2026-07-29`.  
Вебвизор: `YANDEX_METRIKA_WEBVISOR=0`.

Проверка Playwright: `python scripts/tests/metrika_consent_playwright.py`  
Отчёт внутренней статистики: `wp eval-file scripts/wp_internal_stats_report.php`

---

## OAuth

1. [oauth.yandex.ru](https://oauth.yandex.ru/) → **SFRFR Metrika**.
2. Redirect URI: `https://oauth.yandex.ru/verification_code`.
3. Права: `metrika:read`, `metrika:write`.
4. Токен: `access_token=y0_…` в `secrets/yandex-metrika.env`.

```env
YANDEX_METRIKA_EXCLUDE_IPS=1.2.3.4,5.6.7.8
YANDEX_METRIKA_EXCLUDE_MY_IP=1
```

---

## Ensure + smoke

```powershell
python scripts/yandex_metrika_ensure_counter.py
python scripts/yandex_metrika_report_smoke.py
```

Ensure: счётчик, цели, robots-filter, IP exclude, cut_parameter.  
Smoke: management + агрегаты Reports API (без Logs).

---

## Деплой на WP

```bash
sudo bash /opt/sfrfr/scripts/wp_deploy_metrika.sh
sudo -u www-data wp eval-file /opt/sfrfr/scripts/wp_upsert_legal_pages.php --path=/var/www/taxi-doroga-dobra
sudo -u www-data wp eval-file /opt/sfrfr/scripts/wp_fix_sample_page.php --path=/var/www/taxi-doroga-dobra
```

MU: `sfrfr-yandex-metrika.php`, `sfrfr-seo-robots.php` (Clean-param), verification.

---

## Цели на витрине

| Код | Триггер |
|-----|---------|
| `max_click` | клик MAX |
| `cabinet_click` | cabinet.proverkastaza.ru |
| `lead_start` | `#zayavka` / focus формы |
| `tariff_view` | `#tarify` в viewport |
| `lead_ok` | WPForms success |
| `form_error` | WPForms error |

---

## Проверка

1. Без «Разрешить» — нет сети на `mc.yandex.ru`.
2. «Разрешить» → `tag.js` / `watch`.
3. MAX → `max_click`; заявка → `lead_ok`.
4. `python scripts/yandex_metrika_report_smoke.py`.

---

## Пока не включать

- Вебвизор — до маскирования полей формы.
- CRM / offline-конверсии.
- Сырые логи Метрики в BI.
