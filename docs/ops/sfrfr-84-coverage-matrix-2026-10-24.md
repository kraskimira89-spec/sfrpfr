# SFRFR-84: матрица критериев R1 честное резюме (2026-10-24)

**Задача:** [SFRFR-84](https://tracker.yandex.ru/SFRFR-84) · эпик [SFRFR-82](https://tracker.yandex.ru/SFRFR-82)  
**Код:** `src/sfrfr/services/brief_analysis.py` (+ `staff_document_check_result.attach_honest_brief`, `run_brief_after_kit`)  
**Прогон:** `pytest tests/unit/test_brief_analysis_offer.py` → см. раздел «Прогоны» (не смешивать).

Легенда класса: `covered` | `thin` (код есть, тест усилен/нужен) | `gap` | `live`.

| # | Критерий | Участок кода | файл::тест | Что доказано | Класс | Пробел / следующая проверка |
|---|---|---|---|---|---|---|
| 1 | Основание **docs** («подтверждено документами») | `_labeled_from_findings` → `_format_brief_bullet` → `compute_brief_analysis.summary` | `test_findings_drive_discrepancy`; `test_run_brief_delivers_evidence_labels_in_client_body` | Метка в summary и в теле `enqueue_max_delivery` | covered | live MAX: клиент видит метку в чате |
| 2 | Основание **needs_check** («требует проверки») | `_NEEDS_CHECK_THEMES` + `_format_brief_bullet` | `test_questionnaire_themes_are_careful_possible`; delivery в `test_run_brief_delivers_*` | Север/не учли → needs_check + soft-ask | covered | live |
| 3 | Основание **client** («со слов клиента») | `_CLIENT_ONLY_THEMES` | `test_weak_stazh_problem_is_client_only_not_justified`; `test_run_brief_client_only_no_soft_ask_attachments`; UI `test_honest_brief_ui_no_offer_when_client_only` | Слабые даты/стаж → client; без soft-ask | covered | live |
| 4 | ≤3 пункта | `labeled[:_MAX_BRIEF_BULLETS]` | `test_findings_drive_discrepancy`; `test_honest_brief_ui_three_evidence_*`; delivery bullets | Обрезка до 3 | covered | — |
| 5 | Один next step | `_NEXT_STEP_*` в summary / UI | questionnaire / findings / UI tests | Next step в тексте | covered | live читаемость |
| 6 | Слабый goal `check_experience` ≠ discrepancy | `_problem_text(include_goal=False)` | `test_goal_check_experience_alone_not_discrepancy` | Goal не открывает soft-ask | covered | — |
| 7 | Soft-ask / офер только docs\|needs_check | `has_disc = has_docs or has_needs`; `run_brief_after_kit` attachments; `honest_brief_ui_payload.offer_diag_allowed` | `test_run_brief_delivers_soft_ask`; `test_soft_ask_not_sent_without_gaps`; UI no_offer client_only | Кнопки только при justified | covered | live soft-ask |
| 8 | EVIDENCE_* в **пути offer** (не только константы) | `run_brief_after_kit`: `body = result.summary` (+ `_SOFT_ASK`); UI `attach_honest_brief` | `test_run_brief_delivers_evidence_labels_in_client_body` | Метки уходят в delivery body | covered | staff UI smoke (SFRFR-91) |
| 9 | Без «перерасчёт» / гарантий | copy в compute | `test_questionnaire_themes_*` | Нет запрещённых слов в summary | covered | ревью живого текста |
| 10 | Disclaimer подачи/СФР | `_NO_DISCREPANCY_TEXT` / `_DISCLAIMER` | no_discrepancy / themes | Disclaimer в ветках | covered | — |
| 11 | Живая приёмка MAX | `schedule_brief_after_kit` после settle | — | unit ≠ live | **live** | отдельный запрос разрешения на исходящее |

## Путь клиентского offer (факт)

```text
settle комплект → schedule_brief_after_kit
  → run_brief_after_kit
    → compute_brief_analysis  # bullets с (evidence label)
    → persist_brief_to_intake
    → enqueue_max_delivery(body=summary[+soft_ask], attachments=keyboard?)
  → (клик soft-ask) diag_choice → diag_offer_gate (флаги brief)
```

Staff: `attach_honest_brief` / `honest_brief_ui_payload` — те же `EVIDENCE_*` (SFRFR-91 UI).

## Прогоны (не смешивать)

| Когда | Команда | Результат |
|---|---|---|
| До усиления тестов пути offer | `pytest …/test_brief_analysis_offer.py` | **28 passed** (базовый срез) |
| После тестов delivery/evidence | тот же файл | см. PR / локальный отчёт head |

`28 passed` **не** закрывает критерий live и не заменяет матрицу.

## Решение по SFRFR-84 (этот срез)

Канон приёмки (подробно в `sfrfr-84-criteria-evidence-matrix-2026-10-24.md`):

`13 unit + 1 N/A + 1 live MAX + 1 зависимость от SFRFR-85 = 16`.

Staff UI — **вне** этих 16 → **SFRFR-91**.

- Дефекта в коде EVIDENCE/offer **не найдено**.
- Недостаток был в **доказательстве** пути delivery → unit-тесты (без rewrite working code).
- PR **без auto-merge**.
- **Не закрывать** до live MAX smoke **и** согласования зависимости **SFRFR-85**.
- Live / исходящее — только с отдельным разрешением (здесь не запрашивается).
