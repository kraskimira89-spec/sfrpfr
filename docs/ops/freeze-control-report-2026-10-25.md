# Контрольная точка заморозки — 2026-10-25

Заморозка merge/deploy сохраняется. Массовый откат не выполнялся.  
Единственное согласованное изменение состояния в этом цикле: попытка отключить auto-merge #122/#119/#277.

## 1. Auto-merge

| PR | Результат |
|----|-----------|
| #122 | `autoMergeRequest=null` (уже выкл.). `gh pr merge --disable-auto` → GraphQL: can't disable |
| #119 | то же |
| #277 | **уже MERGED** до отключения; auto-merge отключить нельзя |

**#277 факт merge:** `6d17a5a63e3a30211887a53278ae8228c4c536a1` @ `2026-10-25T06:27:11Z`  
**deploy-vps:** run [40169131824](https://github.com/kraskimira89-spec/sfrpfr/actions/runs/40169131824) success (docs-only содержимое, полный VPS deploy всё равно стартовал).  
Revert **не** выполнялся. Журнал: `docs/history/2026-10-25-pr-277-automerge-deviation.md`.

**Прочие open PR (read-only GraphQL):** #39, #41, #42, #45, #61, #119, #122, #269 — у всех `autoMergeRequest=null`. Дополнительных включений нет; молча ничего не менялось.

## 2. Production SHA и runtime

| Поле | Значение |
|------|----------|
| `origin/main` / VPS `/opt/sfrfr` HEAD | `6d17a5a6` (#277 docs) |
| Runtime-код относительно `ef3fc44a` (#273) | `#274` и `#277` — только docs; **runtime ≈ `ef3fc44a`** |

Вошедшие runtime-изменения на развёрнутом дереве (не «принятые» — для диагностики):

| SHA / PR | Что затрагивает | Данные/схема | Наблюдаемый дефект | Безопасный откат кода |
|----------|-----------------|--------------|--------------------|------------------------|
| `ef3fc44a` #273 | period date correction API/repo/store; фоновые не timer | новая логика/таблицы через tools date_op | не зафиксирован здесь | отдельный план (данные) |
| `2d0adc91` #271 | MAX handler E05/F04 + LLM claim filter | нет миграции в PR | не зафиксирован здесь | код откатываем; переписка уже ушедшая — нет |
| `f4027bc9` #260 | fiscal_reconcile exclude receipt_ocr | нет | кандидат-мусор снят | да, узкий |
| `744df452` #259 | tests + docs SFRFR-84 | нет | нет | n/a tests |
| `b2dbdc0d` #261 | llm_chat + большой docs pack | нет | не зафиксирован здесь | код+docs |

HTTP 200 сайта ≠ корректность фоновых задач.

## 3. Production API-smoke (отклонение)

Закрытый журнал: `docs/ops/logs/prod-api-smoke-request-review-2026-10-25.md`.

Кратко: POST `request-review` @ `2026-10-25T06:15:42Z` создал job `d11b298f…` → `needs_action`; outbox/notification_jobs/orders = **0**; pipeline=`human_review`.  
Backend на момент smoke (до deploy #277): runtime **`ef3fc44a`**.  
Повторять без согласования **нельзя**. Записи не удалялись.

## 4. PR #269

| Поле | Значение |
|------|----------|
| Текущий head (не двигать ради диагностики) | `daba9a8a` |
| Старый green | `b65e48f9` |
| Diff `b65e48f9 → 3116e0d9` | **только docs/scripts** (4 файла, +62/−6): supabase2 MCP access, browser-smoke note, dbhub toml |
| После `3116e0d9` | ещё `daba9a8a` — docs smoke-отчёт API |
| statusCheckRollup сейчас | пусто (новых обязательных checks на head нет) |
| Гипотеза anti-abuse | **гипотеза**, не факт |

Полный diff `b65e48f9…3116e0d9` не содержит runtime `src/`. Старый SUCCESS на `b65e48f9` **не** заменяет CI на `daba9a8a`/`3116e0d9`. Merge #269 / обход checks — **запрещены**.

Локальные проверки head — отдельным прогоном на том же SHA (см. § ниже в отчёте исполнителя при наличии).

## 5. Auth/browser-стенд и `needs_action`

| Пункт | План (без prod) |
|-------|-----------------|
| Стенд | изолированный admin + GoTrue preview/Auth-стенд; не api.proverkastaza.ru |
| Дефект | при `needs_action` primary скрывается → сотрудник без явного следующего шага |
| Исправление | матрица действий (открыть результат / чего не хватает / повторить / находки); UI+unit на стенде |
| Не делать | production как замена Auth-стенда |

## 6. SFRFR-93/97

Без изменений: 93 open до create; 97 open (группа B); тики **144**; create = «сценарий не встретился»; checkpoint `2026-10-26T06:00Z±2ч` в журнале исполнителя; job-конфиг не расширять.

## 7. UI фаза 1 (аккордеон 13 ступеней)

Разрешена работа на ветке / PR **без** auto-merge и **без** merge/deploy.  
Тарифы/API/автоматизации не менять в том PR.
