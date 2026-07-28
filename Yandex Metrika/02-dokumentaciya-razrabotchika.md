# Яндекс Метрика — документация для разработчиков (оглавление)

Источники: [API Метрики](https://yandex.ru/dev/metrika/doc/api2/concept/about.html) · [Quick start](https://yandex.ru/dev/metrika/ru/intro/quick-start) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Base management: `https://api-metrika.yandex.net/` · Auth: `Authorization: OAuth <token>` (Яндекс ID).

---

## Виды API

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [About API](https://yandex.ru/dev/metrika/doc/api2/concept/about.html) | Intro | Управление / отчёты / logs / import | **P0** |
| [Quick start](https://yandex.ru/dev/metrika/ru/intro/quick-start) | Start | Первые вызовы | **P0** |
| [Authorization](https://yandex.ru/dev/metrika/ru/intro/authorization) | OAuth scopes | `metrika:read/write/expenses/user_params/offline_data` | **P0** |
| [FAQ API](https://yandex.ru/dev/metrika/ru/faq) | FAQ | Частые ошибки | P1 |

---

## Management API

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Список счётчиков](https://yandex.ru/dev/metrika/doc/api2/management/counters/counters) | GET counters | Найти counter id | **P1** |
| [Цели](https://yandex.ru/dev/metrika/doc/api2/management/goals/goals) | Goals CRUD | Создать цель программно | **P1** |
| [Reporting intro](https://yandex.ru/dev/metrika/doc/api2/api_v1/intro) | Reports API | Статистика через API | **P1** — дашборд ops |
| [Data / reports](https://yandex.ru/dev/metrika/doc/api2/api_v1/data) | Query reports | Метрики и группировки | **P1** |
| [Logs API](https://yandex.ru/dev/metrika/doc/api2/logs/intro) | Raw logs | Неагрегированные хиты | **P2** — осторожно с ПДн |

---

## Клиентский JS (сайт)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Init](https://yandex.ru/support/metrica/code/counter-initialize.html) | ym init | Опции счётчика | **P0** |
| [reachGoal](https://yandex.ru/support/metrica/ru/general/goal-js-event.html) | Events | Цели из WP/JS | **P0** |
| [Создание счётчика](https://yandex.ru/support/metrica/ru/general/creating-counter) | Install | Куда вставить код | **P0** |

Пример безопасной цели:

```js
ym(COUNTER_ID, 'reachGoal', 'lead_submit_ok');
// НЕ передавать phone/email/name в params или URL
```

---

## OAuth scopes (из authorization)

| Scope | Назначение | SFRFR |
|-------|------------|-------|
| `metrika:read` | Чтение счётчиков/статистики | **P1** |
| `metrika:write` | Создание/правка счётчиков | P2 |
| `metrika:expenses` | Расходы рекламы | P2 |
| `metrika:user_params` | Параметры посетителей | **Осторожно** — не ПДн |
| `metrika:offline_data` | CRM / офлайн-конверсии | P2 — только обезличенные id |

Отдельное OAuth-приложение на [oauth.yandex.ru](https://oauth.yandex.ru/) — см. `Yandex ID/`.

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| Цели лид + MAX на витрине | goals · reachGoal · init |
| Запрет ПДн в аналитике | ТЗ-10 · gdpr · не user_params с ФИО |
| Отчёт конверсии в ops | reports api_v1/data |
| Импорт «лид из API» как офлайн | offline_data — только после политики ПДн |
| Вебвизор без утечки форм | webvisor settings + CSS/маскирование |

---

## Уже зафиксировано в проекте

| Тема | Где |
|------|-----|
| Метрика без ПДн в URL/событиях | `docs/specs/10-landing-audit-and-implementation.md` §7 |
| Captcha отдельно | Google сейчас → SmartCaptcha ТЗ-15 |
