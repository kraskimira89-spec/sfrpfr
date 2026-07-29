# Яндекс Метрика — пользовательская документация (оглавление)

Источники: [Help](https://yandex.ru/support/metrica/) · [Метрика UI](https://metrika.yandex.ru/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Сайт: `proverkastaza.ru` · **критично:** не слать ПДн форм/телефоны в URL и события (ТЗ-10 §7).

## Статус SFRFR (исполнение)

| Тема | Статус | Где |
|------|--------|-----|
| Счётчик + init на WP | ✅ после согласия | `docs/ops/yandex-metrika-setup.md` |
| Цели лид / MAX / воронка | ✅ | MU + ensure |
| GDPR: согласие до загрузки | ✅ | баннер на витрине |
| Без ПДн в reachGoal | ✅ | только коды целей |
| Вебвизор | ⏸ выкл. | до маскирования полей |
| Отчёты UI | ✅ кабинет Метрики | counter `111134477` |

---

## Как пользоваться

| Приоритет | Смысл |
|-----------|--------|
| **P0** | Счётчик, цели (лид/MAX CTA), GDPR/ПДн, без ПДн в хитах |
| **P1** | Вебвизор (осторожно с формами), отчёты |
| **P2** | API отчётов / CRM import |

---

## Счётчик и цели

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Help hub](https://yandex.ru/support/metrica/) | Помощь | Оглавление Метрики | **P0** |
| [Создание и установка](https://yandex.ru/support/metrica/ru/general/creating-counter) | Counter | Создать, скопировать код в header | **P0** — WP |
| [Инициализация счётчика](https://yandex.ru/support/metrica/code/counter-initialize.html) | JS init | `ym(id, 'init', …)` параметры | **P0** |
| [Цели — типы](https://yandex.ru/support/metrica/ru/general/goals) | Goals | URL / JS / клик / форма | **P0** — «заявка», «открыть MAX» |
| [Цели (eng path)](https://yandex.ru/support/metrica/general/goals.html) | Goals alt | Дубль/зеркало статьи | P1 |
| [JS-событие цели](https://yandex.ru/support/metrica/ru/general/goal-js-event.html) | reachGoal | `ym(id,'reachGoal','LEAD')` | **P0** — без параметров с ПДн |
| [UI Метрика](https://metrika.yandex.ru/) | Console | Отчёты и настройки | **P0** |
| [Добавить счётчик](https://metrika.yandex.ru/add/) | Add | Мастер создания | **P0** |

---

## Вебвизор и записи

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Вебвизор — описание](https://yandex.ru/support/metrica/ru/webvisor/info) | Webvisor | Запись сессий | **P1** — маскировать поля ПДн |
| [Настройка Вебвизора](https://yandex.ru/support/metrica/ru/webvisor/settings) | Settings | Вкл. в настройках счётчика | **P1** |
| [Требования](https://yandex.ru/support/metrica/ru/webvisor/requirements) | Requirements | 1 вебвизор на сайт, iframe | **P1** |
| [Settings (legacy path)](https://yandex.ru/support/metrica/webvisor/settings.html) | Alt URL | То же | P1 |

---

## ПДн / GDPR

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [GDPR / обработка данных](https://yandex.ru/support/metrica/ru/general/gdpr) | Privacy | Настройки согласия / данные | **P0** |
| [GDPR html](https://yandex.ru/support/metrica/general/gdpr.html) | Alt | Зеркало | **P0** |

**Правило SFRFR:** в `reachGoal` / URL / params — только технические коды (`lead_ok`, `max_click`), **не** ФИО, телефон, email, СНИЛС.

---

## Быстрый указатель

| Задача | Смотреть |
|--------|----------|
| Поставить счётчик на WP | creating-counter · counter-initialize |
| Цель «отправка заявки» | goals · goal-js-event (без ПДн) |
| Цель «клик Открыть в MAX» | goals |
| Включить Вебвизор безопасно | webvisor settings + маскирование полей |
| Согласие на cookies/метрику | gdpr + наши страницы ПДн |
