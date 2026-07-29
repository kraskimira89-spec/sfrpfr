# ТЗ-17: российский контур управленческой аналитики SFRFR

**Статус:** целевой BI утверждён — **dbt marts → Yandex DataLens**; Google Sheets/Looker подлежат полной замене после сверки KPI  
**Дата уточнения:** 2026-07-29  
**Опора:** анализ архитектуры + решение о полной замене Google Таблиц

## 0. Утверждённый целевой контур

### Рекомендуемый (основной)

```text
dbt marts → Yandex DataLens
```

DataLens подключается к обезличенной PostgreSQL-витрине (`analytics.*`) и показывает
управленческие показатели **без** промежуточных Google Sheets / Looker.

Преимущества:

- обновление после nightly dbt (без ручного `sheets-sync`);
- фильтры, графики, KPI-карточки;
- доступ только руководителям (без public link);
- российский контур;
- единый SoT с dbt marts.

### Альтернативы (роль зафиксирована)

| # | Вариант | Роль |
|---|---------|------|
| 1 | **DataLens + PostgreSQL** (`analytics.*`) | **основной** управленческий BI |
| 2 | **Собственный admin SFRFR** | **резервный** интерфейс / аварийный baseline |
| 3 | **amoCRM** (штатный рабочий стол) | **только** продажи и операционная воронка |
| 4 | **Яндекс Таблицы** | **временная** привычная табличная оболочка, **не** основной BI |
| — | Google Sheets + Looker | **на пилоте допустимы**; после сверки KPI — отключение |

### Правило отключения Google

`SheetsExporter` / `sheets-sync` / SA Google Sheets **не удалять**, пока:

1. DataLens workbook закрыт и доступен руководителям;
2. все обязательные KPI §7 сверены с dbt baseline (допуск §11);
3. подписан cutover (владелец аналитики).

После этого: выключить endpoint/кнопку sync → отозвать ключи SA → удалить интеграцию
из целевого контура (код можно оставить за feature-flag на один релиз).

Google Sheets **не** является целевой российской заменой. Яндекс Таблицы — только
если нужен табличный UX на переходный период; источник строк всё равно marts/export
из `analytics.*`, не live API whitelist.

## 1. Цель

Импортозаместить **пользовательский runtime-контур управленческой визуализации** и
**необязательный инструмент разработки**, сохранив воспроизводимый расчёт KPI.

### 1.1 Что заменяем (уточнено анализом)

| Объект | Почему в scope | Приоритет |
|--------|----------------|-----------|
| **Google Sheets** (`SheetsExporter`, `sheets-sync`) + **Looker Studio** (ops поверх Sheets) | иностранный runtime BI; live-экспорт **не читает** `analytics.*` | **P0** |
| **dbt Labs / Cursor plugin** (skill analytics engineering, gap analysis `schema.yml`) | только IDE; не production; `packages.yml` отсутствует | **P1**, можно отключить без остановки продукта |
| **dbt Core** (VPS timer → marts) | **не** цель замены на MVP; baseline трансформаций | вне scope до пилота **T2** |

### 1.2 Что не заменяем этим ТЗ

- операционный `GET /admin/dashboard` (live Supabase, staff);
- amoCRM как CRM/воронка сделок (отдельный sales-пилот, не SoT product KPI);
- FastAPI / кабинеты / MAX / платежи при сбое BI.

Не выбирать единственную BI-платформу «вслепую»: сверка KPI обязательна.  
**Целевой победитель управленческого BI уже выбран:** DataLens поверх dbt marts (§0).  
amoCRM и admin остаются пилотами с **другими** ролями (sales / резерв), не конкурентами DataLens за SoT.

## 2. Важное разделение

```text
Источники (SoT дел)          Расчёт KPI (SoT метрик)     Представление
public.* + analytics_source → dbt Core → analytics marts → DataLens / admin C / …
```

**dbt Core** — batch ELT: обезличенные `analytics_source` → staging views → marts tables;
тесты `schema.yml`; nightly 05:30 МСК; **не UI**.

**dbt Labs plugin в Cursor** — помощь разработчику; **не** дашборд руководителя.

**Параллельный live-контур (не SoT KPI):**

- `GET /admin/analytics` + `POST /admin/analytics/sheets-sync` → Google Sheets
  из `CaseRepository.anonymized_analytics_rows()`;
- семантика колонок **расходится** с dbt (`stage` vs `b2c_status`, `silent_flag` vs
  `silent_180_days`, case-rows vs monthly rollup).

### 2.1 Решение: единый источник управленческих KPI

**Source of truth для управленческих KPI = dbt marts**, прежде всего:

- `analytics.mart_management_dashboard` (агрегаты для executive);
- детализация: `fct_case_funnel`, `fct_payments`, `fct_success_fee`, `fct_silent_cases`,
  `dim_case_segment`.

Следствия:

1. Пилоты DataLens / независимого BI читают **только** `analytics.*` (или read-only
   снимок с тем же grain), а не live Sheets-логику.
2. Admin `/admin/analytics` и Sheets — **временный/ops** канал; не эталон для сверки
   пилотов (кроме явного baseline «как было в Sheets» на этапе 0).
3. При расхождении API ↔ dbt править **потребителя или контракт колонок**, не «подгонять»
   marts под Sheets.

### 2.2 Яндекс Метрика — только веб-воронка

Метрика покрывает **публичный маркетинг** (визиты, источники, CTA, лид-форма, клик в MAX).

**Запрещено** считать Метрику заменой:

- `fct_case_funnel` / оплаты / success fee / silent cases;
- любых post-lead product KPI без явного обезличенного ключа сопоставления.

В DataLens Метрику допускается вынести **отдельной** страницей «Веб», не смешивая с
executive summary по делам.

### 2.3 `stg_communications` (orphan)

Модель `analytics/models/staging/stg_communications.sql` + тесты в `schema.yml`
существуют; **ни один mart на неё не ссылается**. Source
`analytics_source.communications_agg` есть.

**Решение на этап 0 (зафиксировано):**

- **не включать** в обязательный каталог управленческих KPI и в приёмку DataLens POC;
- оставить в dbt как orphan **или** удалить отдельным PR после ревью (бэклог);
- если понадобится метрика «активность коммуникаций» — сначала `ref` в mart + определение
  KPI, затем пилот BI.

Фактический объект импортозамещения runtime:

1. Google Sheets + Looker Studio;
2. необязательный dbt Labs plugin/skill;
3. dbt Core — только отдельный пилот T2 при доказанной избыточности.

## 3. Исходное состояние (карта после анализа)

### 3.1 Два параллельных контура

```text
public.* (SoT дел, ПДн, RLS)
        │
        ├─ security_barrier views ──► analytics_source.*
        │                                    │
        │                                    ▼ nightly dbt (analytics_transformer)
        │                              analytics.* marts  ←── SoT KPI (ТЗ-17)
        │                                    │
        │                                    ▼ пилоты BI (DataLens / …)
        │
        └─ live API ──► CaseRepository.anonymized_analytics_rows()
                              │
                              ├─ GET /admin/analytics
                              └─ SheetsExporter → Google Sheets → Looker (ops)
                                 ↑ не SoT KPI; заменяется в рамках ТЗ-17
```

Схемы `analytics` / `analytics_source` **не** в Supabase Data API
(`schemas = ["public", "graphql_public"]`).

### 3.2 Контур dbt

```text
public → analytics_source (views) → analytics (staging views + marts tables)
```

| Аспект | Факт |
|--------|------|
| Запуск | `sfrfr-dbt.timer` 05:30 Europe/Moscow; timeout 45 мин; user `sfrfr` |
| Build | `dbt debug` → `dbt build --threads 1 --no-populate-cache` → `dbt_apply_rls.sh` |
| CI / `vps_deploy` | **не** включают dbt |
| Packages | `packages.yml` нет — сторонних dbt-пакетов нет |
| Роль | `analytics_transformer`: SELECT `analytics_source`, WRITE `analytics` |

Файлы: `analytics/dbt_project.yml`, `models/staging|marts/`, `schema.yml`,
`scripts/dbt_run.sh`, `scripts/dbt_apply_rls.sh`, `docs/systemd/sfrfr-dbt.*`,
`docs/dbt-analytics.md`.

### 3.3 Модели и KPI (контракт SoT)

| Слой | Модели | Примечание |
|------|--------|------------|
| Sources | `cases`, `orders`, `payments`, `result_evidence`, `communications_agg` | миграция `20260724194001_…` |
| Staging | `stg_cases`, `stg_orders`, `stg_payments`, `stg_result_evidence` | в marts |
| Staging | `stg_communications` | **orphan** — вне KPI SoT (§2.3) |
| Marts | `fct_case_funnel`, `mart_management_dashboard`, `fct_payments`, `fct_success_fee`, `fct_silent_cases`, `dim_case_segment` | SoT |

Пакеты заказов: `DIAG`, `ACCOMP`, `SF_LUMP`, `SF_MONTH`.  
Каналы: `max_miniapp`, `web_cabinet`, `unset`.  
Диапазоны сумм: `0`, `1–5 тыс.`, `5–10 тыс.`, `10+ тыс.`, `unknown`.

### 3.4 Защита данных

В `analytics_source` и `analytics` не допускаются:

- ФИО, телефон, email, СНИЛС;
- тексты сообщений, OCR и документы;
- MAX ID и пользовательские идентификаторы;
- ID платёжного провайдера;
- точные суммы, если достаточно диапазонов.

Схема `analytics`: `REVOKE` + RLS без политик для `anon/authenticated`.

## 4. Кандидаты для пилотов

### Вариант A — Yandex DataLens + существующие dbt-витрины

**Назначение:** основной кандидат для управленческого BI.

```text
analytics_source → dbt Core → analytics marts → DataLens
```

Преимущества:

- российская облачная платформа;
- PostgreSQL-коннектор и интерактивные дашборды;
- фильтры, графики, KPI-карточки;
- минимальная переделка проверенной SQL-логики;
- возможен последующий перенос источника в Yandex Managed PostgreSQL.

Ограничения:

- DataLens — визуализация, не полноценная замена dbt/ETL;
- нельзя публиковать дашборд публично;
- подключение к self-hosted PostgreSQL должно быть безопасным;
- при отсутствии приватного соединения нельзя просто открыть `5432` в интернет.

Безопасные способы подключения рассматриваются в таком порядке:

1. Managed PostgreSQL в Yandex Cloud с разрешённым доступом из DataLens;
2. отдельная обезличенная analytics-replica/БД в РФ;
3. TLS endpoint с read-only ролью и строгим allowlist — только как временный пилот;
4. экспорт уже агрегированных данных в поддерживаемый российский источник.

Официальная инструкция подключения PostgreSQL:
<https://yandex.cloud/ru/docs/datalens/operations/connection/create-postgresql>.

### Вариант B — встроенная аналитика amoCRM

**Назначение:** быстрый пилот для продаж и операционной воронки.

amoCRM может показать:

- новые/успешные/проигранные сделки;
- сделки и суммы по этапам;
- источники лидов;
- цели и прогноз продаж;
- активность и скорость ответа менеджеров;
- собственные виджеты на основе CRM-фильтров.

Официальное описание рабочего стола:
<https://www.amocrm.ru/support/desktop/blocks_of_desktop>.

Ограничения:

- видит только данные, синхронизированные в amoCRM;
- не заменяет аналитику документов, результата проверки и success fee;
- сложнее обеспечить идентичность исторических расчётов;
- сторонний marketplace-виджет добавляет поставщика и риски доступа;
- amoCRM нельзя превращать во второе хранилище ПДн/документов.

Этот вариант рассматривается как **оперативный sales dashboard**, а не полная
замена аналитического контура.

### Вариант C — собственный дашборд SFRFR

**Назначение:** контрольный вариант без внешней BI-платформы.

```text
analytics marts / SQL views → FastAPI admin API → Next.js admin
```

Преимущества:

- текущая реализация уже существует;
- полный контроль доступа и размещение в РФ;
- нет платы за BI-лицензии;
- можно точно повторить бизнес-логику SFRFR;
- минимальный риск передачи данных третьей стороне.

Ограничения:

- графики, фильтры, экспорт и конструктор отчётов разрабатываются самостоятельно;
- выше стоимость развития интерфейса;
- нет полноценного self-service BI для руководителя.

Вариант C является baseline: другие пилоты должны давать не менее точные цифры.

### Вариант D — российская независимая BI-платформа

Кандидаты для второго этапа:

- Visiology;
- Luxms BI;
- Polymatica;
- Форсайт. Аналитическая платформа;
- иной продукт из реестра российского ПО.

Пилотировать только если DataLens не проходит по функционалу, размещению,
стоимости или требованиям доступа. На MVP не покупать enterprise-лицензию без
результатов POC.

### Вариант E — Yandex Metrika (только веб-воронка)

**Scope зафиксирован анализом:** маркетинг публичного сайта, не product BI.

Использовать:

- посещения и источники трафика;
- CTA и конверсия формы лида;
- переходы в MAX/кабинет;
- поведение на публичном лендинге.

Метрика **не заменяет** `fct_case_funnel`, оплаты, success fee и silent cases.
Отдельная страница/виджет в DataLens; сопоставление с лидами — только по
обезличенному campaign/source ключу (если появится). Документация счётчика:
`Yandex Metrika/`.

## 5. Варианты слоя трансформаций

### T1 — оставить dbt Core (рекомендуемый baseline)

dbt Core запускается на собственном VPS/в Yandex Cloud и не требует dbt Cloud.
Удаляется только необязательный IDE-плагин. SQL-модели, тесты и lineage остаются.

Преимущества:

- уже реализовано;
- воспроизводимые модели и тесты;
- минимальный риск расхождения KPI;
- совместимо с DataLens и собственным dashboard.

### T2 — PostgreSQL views/materialized views + Python/systemd

Полная замена dbt:

- SQL переносится в миграции;
- refresh materialized views выполняется systemd/cron;
- проверки качества реализуются SQL/Python-тестами;
- lineage и документация поддерживаются вручную.

Рассматривать только после доказательства, что эксплуатационная сложность dbt
выше стоимости собственной поддержки.

### T3 — Yandex Managed PostgreSQL/ClickHouse + российский ETL

Целесообразно при росте объёма, числа источников и частоты обновления. Это не
первая фаза SFRFR. ClickHouse не вводить только ради нескольких KPI.

## 6. Рекомендуемая стратегия

Не выполнять big-bang: Sheets живёт параллельно до сверки.

```text
Фаза 0: KPI dictionary + SQL controls (зеркала marts)
Фаза 1: DataLens ← analytics.*  (основной BI)          ← СЕЙЧАС
Фаза 2: сверка KPI DataLens ↔ dbt; dual-run со Sheets
Фаза 3: cutover — отключить SheetsExporter / ключи Google
Фаза 4: amoCRM — sales-only; admin — резерв
Фаза 5: Метрика — только веб-страница (опц. в DataLens)
Фаза 6: (опц.) Яндекс Таблицы как временный tabular UX
Фаза 7: решение T2 по dbt только при доказанной избыточности
```

Утверждено:

- **SoT KPI:** dbt marts;
- **управленческий BI:** DataLens;
- **резерв:** admin SFRFR;
- **продажи:** amoCRM;
- **веб:** Яндекс Метрика;
- **Google Sheets/Looker:** временный dual-run → полное отключение;
- **Яндекс Таблицы:** не основной BI;
- **stg_communications:** вне обязательного KPI.

## 7. Единый каталог KPI

Все варианты обязаны использовать одинаковые определения.

### 7.1 Воронка

| KPI | Определение | Источник |
|---|---|---|
| Новые заявки | дела с `b2c_status=lead` за период | cases |
| Всего дел | количество дел в выбранном срезе | `fct_case_funnel` |
| Диагностика оплачена | дело с paid-заказом `DIAG` | orders/payments |
| Сопровождение оплачено | дело с paid-заказом `ACCOMP` | orders/payments |
| Результат подтверждён | актуальное evidence подтверждено | result evidence |
| Success fee начислен | есть `SF_LUMP`/`SF_MONTH` | orders |
| Success fee оплачен | соответствующий заказ paid | orders |
| Средний срок до результата | среднее число дней до подтверждения | funnel |

### 7.2 Операционные KPI

- дела по `pipeline_status`;
- дела по `b2c_status`;
- тишина ≥30/90/150/180 дней;
- конфликты предпочтительного канала;
- без связанного MAX / веб-кабинета;
- pending/paid/canceled платежи;
- фискальный статус платежей;
- распределение каналов MAX / web / unset.

### 7.3 Срезы

- месяц создания;
- сегмент;
- укрупнённый регион;
- тип проблемы;
- предпочтительный канал;
- пакет услуги;
- менеджер/ответственный — только в закрытом контуре amoCRM, если это разрешено.

### 7.4 Денежные показатели

На обезличенном BI:

- использовать диапазоны сумм;
- точные суммы и фискальные данные показывать только авторизованному admin в
  российском закрытом контуре;
- не передавать provider payment ID в DataLens/виджеты.

## 8. Требования к пилоту DataLens

Создать один закрытый workbook:

1. **Executive summary**
   - всего дел;
   - оплачено DIAG/ACCOMP;
   - подтверждено результатов;
   - success fee due/paid;
   - средний срок результата.
2. **Воронка**
   - переходы по стадиям;
   - конверсия;
   - динамика по месяцам.
3. **Операционные риски**
   - silent cases;
   - pending payments;
   - channel conflicts.
4. **Сегменты**
   - регион;
   - problem type;
   - канал.

Требования:

- доступ только конкретной группе руководителей;
- public link/anonymous iframe запрещены;
- подключение read-only;
- SQL access минимальный;
- refresh не реже 1 раза в сутки на пилоте;
- данные только из `analytics.*` или специального read-only dataset;
- журналировать владельца подключения и дату ротации пароля.

## 9. Требования к пилоту amoCRM

Без установки стороннего marketplace-виджета сначала настроить штатный рабочий стол:

- новые сделки;
- сделки по этапам;
- успешные/проигранные;
- источники;
- скорость первого ответа;
- задачи/просрочки;
- оплаты как статус/поле сделки, если уже синхронизированы.

Не передавать в amoCRM:

- документы и OCR;
- СНИЛС;
- медицинские/пенсионные доказательства;
- service-role ключи;
- точные аналитические marts.

Если штатных блоков недостаточно, отдельным решением тестировать один виджет.
Перед установкой документировать:

- разработчика и юрисдикцию;
- запрашиваемые OAuth scopes;
- куда уходят данные;
- срок хранения;
- стоимость;
- процедуру удаления;
- возможность отключения без потери данных.

## 10. Требования к собственному admin dashboard

Сохранить как контрольный и аварийный интерфейс:

- `/api/portal/admin/dashboard`;
- `/api/portal/admin/analytics`;
- role-based access;
- отсутствие публичных ссылок;
- возможность сравнить KPI с DataLens/amoCRM;
- отображение времени последнего обновления аналитики.

В рамках пилота добавить только недостающие визуализации, а не переписывать весь admin.

## 11. Сверка качества

Для каждого KPI сформировать контрольную выборку:

- период: последние 30 дней + один закрытый календарный месяц;
- набор синтетических тестовых дел;
- ожидаемое значение из SQL/dbt baseline;
- значение DataLens;
- значение amoCRM, если KPI там поддерживается;
- значение admin SFRFR.

Допуск:

- счётчики — строго 0% расхождения;
- суммы/диапазоны — строго 0% на одинаковом срезе;
- средние/проценты — расхождение не более 0,1 п.п. из-за округления;
- timestamp/freshness — в пределах заявленного SLA.

Расхождение не исправлять «подгонкой» дашборда. Сначала уточнить grain, timezone,
фильтр статусов и правило дедупликации.

## 12. Матрица выбора

Каждый пилот оценивается по 100-балльной шкале:

| Критерий | Вес |
|---|---:|
| Точность и воспроизводимость KPI | 25 |
| Безопасность и локализация данных | 20 |
| Функциональное покрытие | 15 |
| Простота для руководителя | 10 |
| Стоимость владения | 10 |
| Эксплуатация и мониторинг | 10 |
| Скорость внедрения | 5 |
| Независимость/переносимость | 5 |

Стоп-факторы независимо от суммы:

- публичный доступ к ПДн;
- невозможность read-only подключения;
- отсутствие аудита доступа;
- передача данных иностранному subprocessорy без согласованного основания;
- расхождение обязательных KPI;
- невозможность экспортировать/удалить данные;
- зависимость production API от доступности BI.

## 13. Этапы и задачи

### Этап 0 — инвентаризация

- [x] dbt-плагин = **Cursor/dbt Labs skill** (не runtime); production packages нет.
- [x] Заменяемый runtime: **Google Sheets + Looker Studio**.
- [x] Целевой BI: **dbt marts → DataLens** (§0); Sheets dual-run до cutover.
- [x] SoT управленческих KPI: **dbt marts** (`mart_management_dashboard` + fct_*).
- [x] Яндекс Метрика: **только веб-воронка**, не product KPI.
- [x] `stg_communications`: **orphan** — вне обязательного KPI; удаление/включение в mart — бэклог.
- [ ] Зафиксировать владельца каждого KPI.
- [ ] Создать data dictionary и SQL-контрольные запросы (зеркала marts).
- [ ] Зафиксировать SLA dbt timer (05:30 МСК, 45 мин).
- [x] План отключения Sheets: `docs/ops/datalens-management-bi.md` §5.

### Этап 1 — DataLens POC

- [ ] Выбрать безопасный способ подключения.
- [ ] Создать read-only роль/датасет.
- [ ] Собрать четыре страницы dashboard.
- [ ] Настроить закрытый доступ.
- [ ] Провести сверку KPI и refresh.

### Этап 2 — amoCRM POC

- [ ] Настроить штатные блоки без marketplace.
- [ ] Сверить sales KPI.
- [ ] Зафиксировать непокрытые метрики.
- [ ] При необходимости выбрать один виджет для отдельного security review.

### Этап 3 — admin baseline

- [ ] Добавить timestamp обновления.
- [ ] Дать руководителю те же основные фильтры.
- [ ] Зафиксировать экспорт/скрин отчёта.

### Этап 4 — Yandex Metrika

- [ ] Настроить цели публичной воронки.
- [ ] Не смешивать веб-конверсии с post-lead KPI без явного ключа сопоставления.
- [ ] Зафиксировать, какие показатели передаются в DataLens.

### Этап 5 — решение о dbt

- [ ] Оставить dbt Core или реализовать ограниченный T2-пилот на 1–2 marts.
- [ ] Сравнить время разработки, тесты, восстановление и поддержку.
- [ ] Не удалять dbt до прохождения двух полных циклов обновления новой схемы.

### Этап 6 — cutover Google → DataLens

- [ ] DataLens показывает все KPI §7 с тем же grain, что marts.
- [ ] Таблица сверки: dbt SQL ↔ DataLens — 0% на счётчиках (§11).
- [ ] Руководители пользуются DataLens ≥ 1 полный цикл nightly dbt.
- [ ] Отключить UI/API `sheets-sync` (feature-flag или удаление кнопки).
- [ ] Отозвать Google Sheets SA / ключи; убрать из VPS `.env` `GOOGLE_SHEETS_*`.
- [ ] Looker Studio отчёты архивировать/удалить.
- [ ] (Опц.) Яндекс Таблицы только если нужен tabular UX — из `analytics.*`, не из API.
- [ ] Обновить `docs/ops-runbook.md`: Sheets = legacy removed.

### Этап 7 — выбор / закрытие пилотов

- [ ] Подтвердить: основной = DataLens; резерв = admin; sales = amoCRM.
- [ ] Матрица 100 баллов для фиксации (DataLens vs admin vs amo — разные роли).
- [ ] При провале DataLens (доступ/биллинг YC) — эскалация на admin C + опц. независимый BI.

## 14. Приёмка

- [x] Уточнена цель замены: Sheets/Looker + необязательный dbt IDE-плагин (§1.1).
- [x] SoT KPI = dbt marts; Метрика только веб; `stg_communications` вне обязательного scope.
- [ ] Есть единый каталог KPI с SQL-определениями (зеркало §7 ↔ marts).
- [ ] Минимум два пилота: DataLens и amoCRM/native admin.
- [ ] Обязательные показатели сверены с **dbt baseline**, не с Sheets-логикой.
- [ ] ПДн не выходят за разрешённый контур.
- [ ] BI недоступность не влияет на FastAPI/кабинеты/MAX.
- [ ] Выбранный вариант: владелец, SLA, backup/export, runbook.
- [ ] Документировано, остаётся ли dbt Core (по умолчанию — да, T1).
- [ ] IDE-плагин dbt отключён осознанно (после подтверждения имени в Cursor).
- [ ] Google Sheets исключён из целевого контура или оставлен как временный канал без ПДн.

## 15. Результат ТЗ

**Утверждённый целевой вариант:**

1. **DataLens + dbt Core** — управленческий BI (полная замена Google Sheets/Looker);
2. **amoCRM** — операционная воронка продаж;
3. **Собственный admin** — резерв и ops dashboard;
4. **Яндекс Таблицы** — только временный tabular UX при необходимости;
5. **DataLens + materialized views** — запасной путь, если позже уйдём с dbt (T2).

До cutover (§ этап 6) Sheets остаются dual-run; dbt-модели и admin — контрольный baseline.

## 16. Ключевые пути (для реализации)

```text
analytics/dbt_project.yml
analytics/models/schema.yml
analytics/models/marts/mart_management_dashboard.sql
analytics/models/staging/stg_communications.sql   # orphan
supabase/migrations/20260724194001_analytics_source_and_role.sql
scripts/dbt_run.sh
scripts/dbt_apply_rls.sh
docs/systemd/sfrfr-dbt.timer
docs/dbt-analytics.md
src/sfrfr/integrations/sheets/__init__.py         # заменяемый runtime
src/sfrfr/db/case_repository.py                   # live analytics rows
src/sfrfr/api/routes/admin_portal.py              # /admin/analytics, sheets-sync
```

## 17. Связанные материалы

- `docs/ops/datalens-management-bi.md` — cutover Sheets → DataLens
- `docs/dbt-analytics.md`
- `docs/ops-runbook.md`
- `docs/specs/04-admin-cabinet.md`
- `docs/specs/06-integrations-and-security.md`
- `docs/specs/12-amocrm.md`
- `docs/specs/15-data-localization-ru.md`
- `docs/specs/16-yandex-cloud-terraform.md`
- `Yandex Metrika/` — только веб-воронка
- `prompts/tasks/management-analytics-russian-bi-pilot.md`
