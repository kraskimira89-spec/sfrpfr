# SFRFR-84 — матрица критериев ↔ evidence → offer (2026-10-24)

**Дата проверки (UTC):** 2026-10-24T12:05:19Z  
**Исходный `main` SHA:** `7e18c2ddfc67a509ab1348015737c173f7bf147a`  
**Задача:** [SFRFR-84](https://tracker.yandex.ru/SFRFR-84) · эпик [SFRFR-82](https://tracker.yandex.ru/SFRFR-82)  
**PR доказательств:** https://github.com/kraskimira89-spec/sfrpfr/pull/259 (без auto-merge)

Сокращённая матрица пути: `docs/ops/sfrfr-84-coverage-matrix-2026-10-24.md` (не заменяет эту).

## Источники (без выбора «удобной» трактовки)

| Источник | Что задаёт |
|---|---|
| SFRFR-84 description | docs / client / needs_check; ≤3 + next step; слабый «стаж»/goal ≠ soft-ask |
| SFRFR-82 R1 + history `2026-10-22-max-funnel-honest-brief.md` | те же основания; soft-ask только docs\|needs_check; клик soft-ask ≠ proof (это **SFRFR-85**) |
| Код `main` `brief_analysis.py` | фактическая реализация EVIDENCE_* и `run_brief_after_kit` |

**Противоречий между источниками по тексту критериев SFRFR-84 не найдено.**  
Разделение с соседями: статусы quiet/kit → SFRFR-83; клик soft-ask / paid flags → SFRFR-85; staff UI офера → SFRFR-91.

## Этап Б — путь offer

```text
Вход (docs + intake problem/type + pipeline findings + chat texts)
  → compute_brief_analysis
      evidence: docs | needs_check | client (метки в bullets)
      has_justified_discrepancy = docs ∨ needs_check
  → persist_brief_to_intake
  → enqueue_max_delivery(body=summary[+_SOFT_ASK], attachments?)
  → (кнопка) diag_choice → diag_offer_gate(flags)
```

| EVIDENCE_* | Как определяется | Где используется | Клиент: текст / действие | Подтверждение |
|---|---|---|---|---|
| `docs` | findings → `_labeled_from_findings` | bullet label; `has_disc` | «подтверждено документами»; soft-ask | compute + delivery tests |
| `needs_check` | сильные темы анкеты `_NEEDS_CHECK_THEMES` | то же | «требует проверки»; soft-ask | compute + delivery |
| `client` | слабые темы `_CLIENT_ONLY_THEMES` | bullet; **не** `has_disc` | «со слов клиента»; **без** soft-ask | compute + delivery |
| (пусто) | нет тем/findings | `has_disc=False` | «не выявила очевидных…»; без soft-ask | `test_no_discrepancy_*` / soft_ask_not_sent |

Неизвестного кода EVIDENCE в модели нет; неизвестный status staff-check — зона **SFRFR-83**, не brief.

## Матрица критериев

| Критерий из задачи/R1 | Источник | Участок кода | Файл::тест | Что доказано | Пробел | Следующая проверка | Состояние |
|---|---|---|---|---|---|---|---|
| Различать docs / client / needs_check в пунктах резюме | SFRFR-84 | `_format_brief_bullet`, `_EVIDENCE_LABEL_RU` | `test_findings_*`, `test_questionnaire_*`, `test_weak_stazh_*` | Метки в summary | — | live MAX | реализовано и проверено |
| ≤3 пункта + один next step | SFRFR-84 | `_MAX_BRIEF_BULLETS`, `_NEXT_STEP_*` | findings / UI / delivery | Обрезка и next step | — | live читаемость | реализовано и проверено |
| Слабый goal / «стаж» ≠ soft-ask | SFRFR-84 | `_problem_text(include_goal=False)`, `_CLIENT_ONLY_*` | `test_goal_check_*`, `test_weak_stazh_*`, `test_run_brief_client_only_*` | Нет justified / нет attachments | — | — | реализовано и проверено |
| Soft-ask / paid-путь только docs\|needs_check | SFRFR-84 / R1 | `has_disc`, `run_brief_after_kit`, `offer_diag_allowed` | soft_ask / UI / delivery | Кнопки только при justified | — | live soft-ask | реализовано и проверено |
| EVIDENCE в **рабочем** пути offer (не константы) | ТЗ волны §5 | `body=result.summary` → `enqueue_max_delivery` | `test_run_brief_delivers_evidence_labels_in_client_body` | Метки в delivery body | — | live | реализовано и проверено |
| R1-1: offer не заявляет доказанным недоказанное | R1 checklist | labels + `has_disc` | themes / findings / client_only | docs≠client в тексте | — | live | реализовано и проверено |
| R1-2: получение docs / проверка / эксперт не смешиваются | R1 | brief после settle; статусы kit → **83** | status loop + brief | Brief не пишет «проверка идёт» | смешение quiet — 83 | smoke 83+84 | реализовано и проверено *(в зоне 84)*; quiet — **SFRFR-83** |
| R1-3: неполнота ≠ положительный вывод | R1 | empty → `_NO_DISCREPANCY_TEXT` (осторожный), client-only без офера | `test_no_discrepancy_*`, client_only | Нет soft-ask на пустоте/client | — | — | реализовано и проверено |
| R1-4: неизвестное evidence | R1 | нет unknown EVIDENCE | — | N/A в модели | — | — | требуется уточнение требования *(не применимо / нет кода evidence)* |
| R1-5: текст+кнопки+next step = одно состояние | R1 | summary + attachments вместе | delivery / soft_ask_not_sent | Согласованы | — | live | реализовано и проверено |
| R1-6: повтор на тех же данных | R1 | skip если `fp`+`SUMMARY_SHOWN` | `test_run_brief_skips_repeat_delivery_when_fingerprint_unchanged` | Второй delivery не уходит | — | live | реализовано и проверено |
| R1-7: актуальность сохранённого результата | R1 | `FP_KEY`, `gate_flags… analysis_current` | `test_brief_stale_*`, UI stale | Stale при смене docs/case | — | — | реализовано и проверено |
| R1-8: нет last_error/секретов в brief-тексте | R1 | brief не читает `last_error` | themes (нет техполей); path design | Не вставляется | — | регрессия copy | реализовано и проверено |
| R1-9: нет обещания результата услуги / исходящего «напишем» | R1 | `_SOFT_ASK`, disclaimer | questionnaire (нет перерасчёт/гарант) | Soft-ask = вопрос+цена+СФР | формулировка «план действий» мягкая | live copy | реализовано и проверено *(с оговоркой copy)* |
| Клик soft-ask ≠ proof анализа | SFRFR-82 R1 #2 | `preserve_gaps*` | tests soft-ask preserve | Частично в offer suite | полный критерий | **SFRFR-85** | требуется живая приёмка / владелец **SFRFR-85** |
| Живой MAX: комплект → резюме → soft-ask | R1 / wave | `schedule_brief_after_kit` | — | unit ≠ live | исходящее | **live** + разрешение | требуется живая приёмка |
| Staff UI честного резюме | SFRFR-91 | `honest_brief_ui_payload` | UI unit tests | Payload готов | UI кабинет | **SFRFR-91** | реализовано и проверено *(unit)*; live UI — 91 |

## Прогоны (не смешивать)

| Момент | Команда | SHA | Результат |
|---|---|---|---|
| Базовый срез до усиления | `pytest tests/unit/test_brief_analysis_offer.py` | `7e18c2dd` (main) | **28 passed** |
| PR #259 head (labels + client-only path) | то же | `2abe9253` | **31 passed** |
| После теста идемпотентности + смежная | `pytest test_brief_analysis_offer + test_max_diag_choice + test_client_case_status_loop` | новый head PR #259 | **75 passed** (локально; CI на head) |

Смежная регрессия (рекомендуется на head):  
`pytest tests/unit/test_brief_analysis_offer.py tests/unit/test_max_diag_choice.py tests/unit/test_client_case_status_loop.py`

## Решение

- Дефекта реализации EVIDENCE→offer **не подтверждено**.
- Пробелы были в **доказательствах** (delivery labels, client-only delivery, idempotent skip) → только тесты + матрицы.
- Кодовый rewrite не требуется.
- SFRFR-84 **не закрывать** до live MAX smoke.
- Live-запрос — отдельный пакет (ниже черновик); **не** исполнять без разрешения.

### Черновик запроса live (не разрешение)

```text
Проверяемый критерий: SFRFR-84 — клиент видит метки docs/needs_check/client и soft-ask только при justified
Среда: production MAX + VPS после deploy #259 (когда смержен)
Тестовый пользователь / чат: синтетический MAX user владельца (не клиент)
Синтетические данные: тестовый комплект ИЛС+ТК без ПДн реального клиента
Точные действия: settle комплекта → дождаться brief → проверить текст меток и наличие/отсутствие soft-ask
Внешние эффекты: 1–2 исходящих сообщения в тестовый чат MAX
Ожидаемый результат: метки в тексте; soft-ask только при needs_check/docs
Очистка: пометить дело test/lost (статус, не delete)
Условие остановки: любое сообщение не в тестовый чат / ПДн / платёж
```
