# Задание агенту: пилоты российской управленческой аналитики SFRFR

Подготовь реализацию пилотов по ТЗ:

`@docs/specs/17-management-analytics-russian-bi.md`

## Контекст

Текущий контур:

```text
public
  → analytics_source (обезличенные views)
  → dbt Core / analytics marts
  → admin SFRFR / Google Sheets + предполагаемый Looker Studio
```

dbt IDE plugin/skill — только инструмент разработки. Не удаляй dbt Core и SQL marts,
пока пилоты не сверены по KPI.

Фактическая runtime-замена — Google Sheets/Looker Studio. dbt Labs plugin заменяется
только как необязательный developer tool.

## Цель первой итерации

Не выбирать победителя заранее. Подготовить три сравнимых POC:

1. Yandex DataLens — полный управленческий dashboard.
2. Встроенный dashboard amoCRM — sales/операционные KPI.
3. Admin SFRFR — контрольный baseline.
4. Yandex Metrika — только публичная веб-воронка.

Независимые BI (Visiology/Luxms/Polymatica) — только shortlist без установки.

## Обязательные действия

1. Прочитать:
   - `docs/dbt-analytics.md`;
   - `analytics/models/schema.yml`;
   - все `analytics/models/marts/*.sql`;
   - admin endpoints/UI аналитики;
   - ТЗ-15 по локализации.
2. Сформировать data dictionary KPI с:
   - названием;
   - grain;
   - SQL-источником;
   - фильтрами;
   - timezone;
   - freshness/SLA.
3. Подготовить SQL-контрольные запросы без ПДн.
4. Для DataLens:
   - выбрать безопасный read-only источник;
   - не открывать PostgreSQL `5432` в интернет без allowlist/TLS;
   - запретить public link;
   - описать workbook/datasets/charts/filters.
5. Для amoCRM:
   - сначала штатные блоки;
   - перечислить покрытые и непокрытые KPI;
   - не ставить marketplace-виджет без security review.
6. Для admin:
   - использовать как baseline;
   - предложить только минимальные недостающие визуализации.
7. Для Метрики:
   - ограничить scope трафиком, CTA и отправкой формы;
   - не считать её заменой оплат/product funnel.
8. Выбрать единый SoT KPI; не сохранять навсегда дублирование dbt marts и live API.
9. Проверить orphan-модель `stg_communications`: подключить к mart либо исключить.
10. Подготовить таблицу сверки KPI и матрицу выбора на 100 баллов.

## Ограничения

- Не изменять production и не удалять dbt.
- Не подключать BI к `public.*`, `auth.*`, `storage.*`.
- Не передавать ФИО, контакты, СНИЛС, документы, OCR, MAX ID.
- Не публиковать dashboard анонимно.
- Не переносить точные суммы в обезличенный BI без отдельного решения.
- Не делать BI зависимостью FastAPI/кабинетов/MAX.
- Не возвращать Google Sheets как целевую российскую замену.

## Артефакты первой итерации

Подготовь в репозитории:

```text
docs/analytics/
├── kpi-catalog.md
├── datalens-poc.md
├── amocrm-dashboard-poc.md
├── admin-baseline.md
├── reconciliation.md
└── decision-matrix.md
```

SQL-контрольные запросы — в:

```text
analytics/audit/
```

Не создавай credentials, API keys, реальные DataLens connections и amoCRM widgets
без подтверждения пользователя.

## Финальный отчёт

Укажи:

- что dbt делает сейчас и что именно заменяется;
- покрытие KPI по каждому варианту;
- риски безопасности/локализации;
- стоимость и эксплуатационную сложность;
- блокеры пилота;
- следующую безопасную задачу;
- предварительную рекомендацию, но не окончательный выбор до тестирования.
