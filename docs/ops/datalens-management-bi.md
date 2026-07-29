# DataLens: управленческий BI поверх dbt marts (ТЗ-17)

**Целевой контур:** `dbt marts → Yandex DataLens`  
**Заменяет:** Google Sheets + Looker Studio  
**SoT KPI:** `analytics.mart_management_dashboard` (+ fct_* для drill-down)  
**ТЗ:** [../specs/17-management-analytics-russian-bi.md](../specs/17-management-analytics-russian-bi.md)

> `SheetsExporter` **не отключать**, пока не закрыт чеклист cutover (§5).

---

## 1. Целевая схема

```text
public.* → analytics_source → dbt nightly → analytics.*
                                              ↓
                                    Yandex DataLens (закрытый workbook)
```

Без промежуточных таблиц Google. Обновление KPI = успешный `sfrfr-dbt.timer` (05:30 МСК).

---

## 2. Роли альтернатив

| Вариант | Когда |
|---------|--------|
| DataLens + PostgreSQL | основной BI |
| Admin SFRFR | резерв / ops |
| amoCRM | только продажи |
| Яндекс Таблицы | временный tabular UX (не основной BI) |
| Google Sheets | dual-run на пилоте → удалить |

---

## 3. Подключение DataLens (шаги)

1. Убедиться, что биллинг облака `sfrfr-ai` разблокирован
   ([yandex-cloud-billing-unblock.md](yandex-cloud-billing-unblock.md)).
2. Каталог с `folder_id` для аналитики (сейчас staging: `b1g0mhpm9tr4lrurk1bu` в `sfrfr-ai`).
3. Источник данных — **только** схема `analytics` (read-only роль), не `public` / `auth` / `storage`.
4. Безопасный доступ к Postgres (порядок предпочтения):
   1. Managed PostgreSQL / replica analytics в YC с доступом DataLens;
   2. TLS + allowlist IP DataLens на analytics endpoint;
   3. **не** открывать `5432` в интернет «для удобства».
5. Создать connection PostgreSQL в DataLens:
   [дока](https://yandex.cloud/ru/docs/datalens/operations/connection/create-postgresql).
6. Datasets минимум:
   - `mart_management_dashboard`;
   - `fct_case_funnel` (опц. drill-down);
   - `fct_silent_cases` / `fct_payments` по необходимости.
7. Workbook: 4 страницы из ТЗ-17 §8 (Executive / Воронка / Риски / Сегменты).
8. Доступ: только группа руководителей; **public link запрещён**.

---

## 4. Сверка KPI перед cutover

Период: последние 30 дней + один закрытый месяц.

| KPI | SQL baseline | DataLens | Δ |
|-----|--------------|----------|---|
| cases_total | `mart_management_dashboard` | … | 0% |
| diagnostic_paid_cases | same | … | 0% |
| service_paid_cases | same | … | 0% |
| result_confirmed_cases | same | … | 0% |
| success_fee_due/paid | same | … | 0% |
| silent_180_days_cases | same | … | 0% |
| avg_days_to_result | same | … | ≤0,1 п.п. |

Сверять с **dbt**, не с колонками Google Sheets (семантика расходится).

---

## 5. Cutover: отключение Google Sheets

После зелёной сверки и ≥1 ночи dbt с живым DataLens:

1. [ ] Сообщить владельцу аналитики: dual-run закончен.
2. [ ] Убрать кнопку / вызов `POST /admin/analytics/sheets-sync` (или feature-flag off).
3. [ ] CLI `sfrfr sheets-sync` — пометить deprecated / удалить из runbook.
4. [ ] На VPS удалить `GOOGLE_SHEETS_*` из `/opt/sfrfr/.env`, restart API.
5. [ ] Отозвать ключ SA Google Sheets в GCP.
6. [ ] Удалить/архивировать Looker-отчёты.
7. [ ] Запись в `docs/history/`.
8. [ ] (Опц. позже) удалить модуль `integrations/sheets` из кода.

Код `SheetsExporter` до пункта 8 можно оставить мёртвым за флагом — не удалять в день cutover без регрессии admin.

---

## 6. Яндекс Таблицы (опционально)

Только если руководителям нужен «как Excel»:

- выгрузка **из** `analytics.*` / DataLens export;
- **не** восстанавливать live API whitelist как SoT;
- не считать заменой DataLens.

---

## 7. Чеклист готовности пилота

- [ ] dbt nightly зелёный
- [ ] DataLens connection read-only на `analytics`
- [ ] workbook 4 страницы, без public link
- [ ] сверка KPI заполнена
- [ ] Sheets ещё включены (dual-run) **или** уже cutover по §5
