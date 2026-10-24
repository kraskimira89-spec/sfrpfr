# SFRFR-84 — матрица критериев ↔ evidence → offer (2026-10-24)

**Дата проверки (UTC):** 2026-10-24T12:05:19Z (матрица); синхрон арифметики — follow-up PR #259
**Исходный `main` SHA:** `7e18c2ddfc67a509ab1348015737c173f7bf147a`  
**Задача:** [SFRFR-84](https://tracker.yandex.ru/SFRFR-84) · эпик [SFRFR-82](https://tracker.yandex.ru/SFRFR-82)  
**PR доказательств:** https://github.com/kraskimira89-spec/sfrpfr/pull/259 (без auto-merge)

Сокращённая матрица пути: `docs/ops/sfrfr-84-coverage-matrix-2026-10-24.md` (не заменяет эту).

## Арифметика приёмки (канон)

```text
13 unit + 1 N/A + 1 live MAX + 1 зависимость от SFRFR-85  =  16
```

| Класс | Кол-во | Смысл |
|---|---:|---|
| unit | 13 | реализовано и проверено unit-тестами в зоне SFRFR-84 |
| N/A | 1 | R1-4: неизвестный код EVIDENCE в модели отсутствует |
| live MAX | 1 | исходящее в чат — только с разрешением |
| зависимость SFRFR-85 | 1 | клик soft-ask ≠ proof; закрытие 84 **зависит** от SFRFR-85 |

**Вне этих 16:** Staff UI честного резюме → **[SFRFR-91](https://tracker.yandex.ru/SFRFR-91)** (не входит в сумму 16).

## Источники (без выбора «удобной» трактовки)

| Источник | Что задаёт |
|---|---|
| SFRFR-84 description | docs / client / needs_check; ≤3 + next step; слабый «стаж»/goal ≠ soft-ask |
| SFRFR-82 R1 + history `2026-10-22-max-funnel-honest-brief.md` | soft-ask только docs\|needs_check; клик soft-ask ≠ proof (**SFRFR-85**) |
| Код `main` `brief_analysis.py` | фактическая реализация EVIDENCE_* и `run_brief_after_kit` |

**Противоречий между источниками по тексту критериев SFRFR-84 не найдено.**  
Соседи: quiet/kit → SFRFR-83; клик soft-ask / paid flags → SFRFR-85; staff UI → SFRFR-91.

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

Неизвестного кода EVIDENCE в модели нет → строка R1-4 = **N/A** (не «уточнение требования»).

## Матрица критериев (16 строк приёмки)

| # | Класс | Критерий | Источник | Участок кода | Файл::тест | Состояние |
|---|---|---|---|---|---|---|
| 1 | unit | Различать docs / client / needs_check | SFRFR-84 | `_format_brief_bullet`, `_EVIDENCE_LABEL_RU` | `test_findings_*`, `test_questionnaire_*`, `test_weak_stazh_*` | реализовано и проверено |
| 2 | unit | ≤3 пункта + один next step | SFRFR-84 | `_MAX_BRIEF_BULLETS`, `_NEXT_STEP_*` | findings / UI / delivery | реализовано и проверено |
| 3 | unit | Слабый goal / «стаж» ≠ soft-ask | SFRFR-84 | `_problem_text(include_goal=False)`, `_CLIENT_ONLY_*` | `test_goal_check_*`, `test_weak_stazh_*`, `test_run_brief_client_only_*` | реализовано и проверено |
| 4 | unit | Soft-ask / paid-путь только docs\|needs_check | SFRFR-84 / R1 | `has_disc`, `run_brief_after_kit`, `offer_diag_allowed` | soft_ask / UI / delivery | реализовано и проверено |
| 5 | unit | EVIDENCE в **рабочем** пути offer | ТЗ волны §5 | `body=result.summary` → `enqueue_max_delivery` | `test_run_brief_delivers_evidence_labels_in_client_body` | реализовано и проверено |
| 6 | unit | R1-1: offer не заявляет доказанным недоказанное | R1 | labels + `has_disc` | themes / findings / client_only | реализовано и проверено |
| 7 | unit | R1-2: получение docs / проверка / эксперт не смешиваются *(зона 84)*; quiet — **SFRFR-83** | R1 | brief после settle | status loop + brief | реализовано и проверено |
| 8 | unit | R1-3: неполнота ≠ положительный вывод | R1 | empty → осторожный текст; client-only без офера | `test_no_discrepancy_*`, client_only | реализовано и проверено |
| 9 | **N/A** | R1-4: неизвестное evidence | R1 | нет unknown EVIDENCE в модели | — | **N/A** |
| 10 | unit | R1-5: текст+кнопки+next step = одно состояние | R1 | summary + attachments вместе | delivery / soft_ask_not_sent | реализовано и проверено |
| 11 | unit | R1-6: повтор на тех же данных | R1 | skip если `fp`+`SUMMARY_SHOWN` | `test_run_brief_skips_repeat_delivery_when_fingerprint_unchanged` | реализовано и проверено |
| 12 | unit | R1-7: актуальность сохранённого результата | R1 | `FP_KEY`, `gate_flags… analysis_current` | `test_brief_stale_*`, UI stale | реализовано и проверено |
| 13 | unit | R1-8: нет last_error/секретов в brief-тексте | R1 | brief не читает `last_error` | themes; path design | реализовано и проверено |
| 14 | unit | R1-9: нет обещания результата услуги / исходящего «напишем» | R1 | `_SOFT_ASK`, disclaimer | questionnaire | реализовано и проверено *(оговорка copy)* |
| 15 | **live MAX** | Живой MAX: комплект → резюме → soft-ask | R1 / wave | `schedule_brief_after_kit` | — | требуется живая приёмка + разрешение |
| 16 | **SFRFR-85** | Клик soft-ask ≠ proof анализа | SFRFR-82 R1 #2 | `preserve_gaps*` | suite soft-ask preserve (частично) | **зависит от SFRFR-85**; 84 не закрывать без этого |

### Вне суммы 16

| Тема | Очередь | Примечание |
|---|---|---|
| Staff UI честного резюме | **SFRFR-91** | `honest_brief_ui_payload` unit есть; live UI / кабинет — не строка 16 |

## Прогоны (не смешивать)

| Момент | Команда | SHA | Результат |
|---|---|---|---|
| Базовый срез до усиления | `pytest tests/unit/test_brief_analysis_offer.py` | `7e18c2dd` (main) | **28 passed** |
| PR #259 (labels + client-only path) | то же | `2abe9253` | **31 passed** |
| После идемпотентности + смежная | `test_brief_analysis_offer` + `test_max_diag_choice` + `test_client_case_status_loop` | `ebe3eb2d` | **75 passed** (локально; CI зелёный) |

## Решение

- Дефекта реализации EVIDENCE→offer **не подтверждено**.
- Пробелы были в **доказательствах** → только тесты + матрицы; rewrite working code не нужен.
- **Закрытие SFRFR-84** — только после:
  1. live MAX smoke (строка 15) с отдельным разрешением;
  2. согласования зависимости **SFRFR-85** (строка 16: клик ≠ proof).
- Staff UI не блокирует арифметику 16; ведётся в **SFRFR-91**.
- Auto-merge PR #259 **не** включать без решения Стратега.

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
