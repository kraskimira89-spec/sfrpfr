# Статус реализации marketing-sales (аудит)

**Дата:** 2026-08-09  
**Источник:** [spec-marketing-sales-foundation.md](../spec-marketing-sales-foundation.md), стратегия, исследование.

## Сводка

| Слой | Статус |
|------|--------|
| Документы foundation | DONE |
| Этап 0–1 (UTM, CRM-атрибуция, baseline) | PARTIAL → in-repo реализация в этом проходе |
| Этап 2 (сегментные страницы, MAX §10.1) | PARTIAL → in-repo |
| Этап 3–4 (реклама, B2B discovery) | NOT DONE / BLOCKED (владелец) |
| Success fee на публичных тарифах | DONE (не публикуется; опция только в Заказе по решению 14.08.2026) |

## P0 — Управление и измерение

| # | Задание | Статус | Комментарий |
|---|---------|--------|-------------|
| 1 | Владелец воронки | BLOCKED | Нужен владелец |
| 2 | Рекламодатель, лимит расходов | BLOCKED | Бюджет утверждает владелец |
| 3 | Baseline метрик | BLOCKED | Цифры из живых кабинетов |
| 4 | Справочник UTM | DONE (код) | `src/sfrfr/marketing/attribution.py` |
| 5 | Поля CRM атрибуции | DONE (код) | amoCRM `LEAD_FIELD_SPECS` |
| 6 | Отчёт до оплаты | PARTIAL | Шаблон weekly; dbt UTM-mart — позже |
| 7 | Сценарий квалификации + потери | DONE (docs) | playbook-sales-qualification |
| 8 | Success fee / цена / юр. | DONE | Решение 14.08.2026: SF допустим только как опция Заказа; в MVP не продаём |
| 9 | Яндекс Бизнес dual ID | BLOCKED | Ручная сверка UI |
| 10 | Развести baseline SEO/ads/product | PARTIAL | Зафиксировано здесь |
| 11 | MAX channel click→pay | PARTIAL | Цели `max_channel_click`; E2E в живой Метрике — владелец |
| 12 | Юр. оферта | DONE | Редакция `offer-2026-08-14` + decision-success-fee |
| 13 | Редакционный стандарт | DONE (docs) | playbook-editorial-standard |
| 14 | ТЗ-10 superseded | DONE | Баннер в ТЗ-10 |

## P1 — Страницы, MAX, тесты каналов

| Задание | Статус |
|---------|--------|
| 3 сегментные коммерческие страницы | DONE (ассеты + seed) |
| 3–5 гипотез на сегмент | PARTIAL | Север: 5 гипотез в `research-segment-north-2026-08.md` (2026-08-10). Родственники / предпенсия — ещё нет. Запуск — владелец. |
| Тесты Яндекс/VK/ОК | BLOCKED |
| Маркированное продвижение канала MAX | PARTIAL (канал есть; платный запуск — владелец) |
| Retargeting | BLOCKED |
| Еженедельный разбор | PARTIAL (шаблон отчёта) |

## P2 / P3

| Задание | Статус |
|---------|--------|
| Partner one-pager | DONE (черновик playbook) |
| Referral codes в проде | PARTIAL (поле `REFERRAL_CODE`; выдача — нет) |
| B2B интервью / ICP / multi-tenant | BLOCKED |

## Что осталось владельцу (BLOCKED)

1. Назначить владельца воронки и месячный лимит рекламы.  
2. Снять baseline из Метрики и amoCRM.  
3. ~~Юр. проверка оферты и решение по success fee.~~ → DONE 14.08.2026 (`decision-success-fee-2026-08-14.md`, оферта `offer-2026-08-14`).  
4. Карточка Яндекс Бизнеса: канон `82469923047`, дубликат удалён (2026-08-12).  
5. ~~Создать цели §7.2~~ DONE 2026-08-14 (ensure + путь канала MAX).  
6. Запустить узкие тесты Директ / VK / ОК с ERID.  
7. B2B discovery (15–20 интервью).

## First-party cookie атрибуции

- Имя: `sfrfr_attr` (JSON: first/last touch UTM).  
- Срок: **90 дней**.  
- Назначение: first-touch / last-touch для lead API; без ПДн.  
- Согласие формы покрывает связь и обработку обращения; аналитика Метрики — только после согласия cookies.


