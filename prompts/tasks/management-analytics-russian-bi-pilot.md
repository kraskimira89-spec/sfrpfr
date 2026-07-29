# Задание агенту: пилоты российской управленческой аналитики SFRFR

ТЗ: `@docs/specs/17-management-analytics-russian-bi.md`  
Ops cutover: `@docs/ops/datalens-management-bi.md`

## Утверждённый целевой контур

```text
dbt marts → Yandex DataLens     ← основной управленческий BI
```

Полная замена **Google Sheets + Looker Studio**.  
`SheetsExporter` отключать **только** после сверки всех KPI с dbt baseline.

### Роли

1. **DataLens + PostgreSQL** — основной BI.
2. **Admin SFRFR** — резервный интерфейс.
3. **amoCRM** — только продажи / операционная воронка.
4. **Яндекс Таблицы** — временный tabular UX, не основной BI.

## Контекст

```text
public → analytics_source → dbt Core → analytics marts → DataLens
                                                      ↘ (dual-run) Sheets — до cutover
```

dbt Core и SQL marts не удалять. dbt IDE plugin — необязателен.

## Цель итерации

1. Поднять POC DataLens на `analytics.*` (read-only).
2. Сверить KPI §7 ТЗ-17 с marts.
3. Описать dual-run и чеклист отключения Sheets.
4. Зафиксировать amoCRM (sales) и admin (резерв) без конкуренции за SoT.
5. Метрика — только веб-воронка.

## Обязательные действия

1. Прочитать ТЗ-17, `docs/dbt-analytics.md`, marts SQL, `docs/ops/datalens-management-bi.md`.
2. Data dictionary KPI + SQL controls от **marts** (не от Sheets columns).
3. DataLens: безопасный PG-коннект; без public link; workbook §8.
4. amoCRM: штатные блоки; непокрытые KPI списком.
5. Admin: baseline / резерв.
6. Не считать Метрику product KPI.
7. `stg_communications` — orphan, вне обязательного scope.
8. Таблица сверки + план cutover Google (§5 ops).

## Ограничения

- Не отключать Sheets до зелёной сверки.
- Не подключать BI к `public` / `auth` / `storage`.
- Не публиковать dashboard анонимно.
- Не делать BI зависимостью API/кабинетов/MAX.
- Не предлагать Google Sheets как целевую РФ-замену.

## Артефакты

- SQL controls + таблица сверки KPI.
- Описание DataLens connection/workbook.
- Чеклист cutover Sheets (ссылка на ops).
- Shortlist: что остаётся в admin / amoCRM.
