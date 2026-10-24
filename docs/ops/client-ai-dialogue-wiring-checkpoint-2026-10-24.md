# Контрольная точка SFRFR-110 / PR #261 (2026-10-24)

**Статус приёмки:** реализация политик и unit-тестов — да; **завершённая приёмка live-пути — нет**.  
Head: `f5822dbd…` (+ последующие коммиты checkpoint). Merge / deploy / live MAX — **не** разрешены этим документом. Auto-merge OFF. SFRFR-110 не закрывать.

## 1. Состав PR #261 (фактический)

| Слой | Содержание |
|---|---|
| Спецификация / каталоги | `docs/specs/client-ai-dialogue-quality.md`, ops matrix/catalog/complex/message/transition/conflicts |
| Исполняемые политики (библиотека) | `*_policy.py`, `deception_*`, `transition_contract_policy`, `multi_intent_policy`, … |
| Действующий клиентский путь | в основном **system prompt** в `llm_chat.py`; **прямой вызов политик из handler отсутствует** |
| Тесты | `tests/unit/test_*_policy.py`, `test_client_ai_complex_dialogues.py`, JSON `client_ai_complex_dialogues.json` |

## 2. Подключение: требование → код → live

| Требование | Функция | Место вызова | Источник фактов | Тест | Live-путь |
|---|---|---|---|---|---|
| Ответ при ошибке только из фактов | `build_confirmed_error_reply` / `client_facing_error_reply` | **нет** в handler; только unit | `facts[]` от вызывающего; persist — см. ниже | `test_deception_client_reply_policy`, `test_deception_negative_guards` | **библиотека** (+ намёк в system prompt) |
| Persist «дата исправлена» | `persist_flag_is_trusted` + `date_persist_succeeded` | нет в handler | **только** `db_write_ack` / `repository_update_ok` / `job_event_persisted`; запрещены `llm_self_report`, `prompt_filled_flag` | `test_llm_persist_flag_not_trusted` | **не подключено** к записи в БД |
| Fallback при неполных данных | `client_facing_error_reply` → `SAFE_INCOMPLETE_FACTS_FALLBACK` | нет в handler | — | `test_incomplete_uses_fallback_not_silence` | **библиотека** |
| Обвинение / составные требования | `classify_deception_signal`, `split_deception_compound` | `parse_multi_intent` (тоже **не** в handler) | текст клиента | `test_deception_*`, multi_intent | **библиотека** |
| Переходы said≠done, provisional | `refined_error_pipeline`, `announce_fix_allowed`, … | нет в handler | контрактные флаги в тестах | `test_deception_transition_refine`, negative | **библиотека** |
| Доказательства (карточка) | `evidence_card_skeleton`, статусы | нет persist | логическая схема | `test_deception_evidence_contract` | **контракт; долговременная фиксация не подтверждена** |
| Запреты риторики / offer | `reply_has_banned_*`, offer gates | нет enforced post-filter в handler | — | unit + JSON must_not | **prompt-only** (модель может нарушить) |
| Статус проверки queued≠running | (SFRFR-83 на main + контракт) | check status path (частично вне #261) | события job | transition / SFRFR-83 | **частично live** (не весь каталог E*) |

### Persist — явно

Флаг `date_persist_succeeded=True`, который «заполнила модель» или промпт, **не** доказательство сохранения.  
Доказательство — ack записи хранилища / репозитория / job-event. Пока handler не передаёт такой ack в `client_facing_error_reply`, формулировка «Дата исправлена в деле» **не должна** уходить клиенту из этой библиотеки в проде.

## 3. Граница «без новой БД»

| Утверждение | Оценка |
|---|---|
| Новая таблица не вводилась | Да |
| Логический контракт evidence / переходов реализован в Python | Да (unit) |
| Долговременная фиксация evidence-card, связей версий, аудита просмотра | **Не подтверждена** |
| Существующие механизмы (`result_evidence` и т.п.) обеспечивают диалоговые доказательства | **Нет** — `result_evidence` про суммы пенсии; не перегружать |

Формулировка для отчётов: *«контракт реализован; долговременная фиксация и интеграция в клиентский путь не подтверждены»*.

## 4. Реализовано vs осталось (SFRFR-110)

**Сделано (библиотека + доки + unit):** сценарии 20.18–20.26 / §49–72; JSON S20.*; политики; негативные guards; fallback; CI api/cabinet/admin на head.

**Осталось для приёмки live:**

1. Вызов политик из MAX/cabinet reply path (не только system prompt).  
2. Подача system-ack persist / registration в builder.  
3. Post-filter исходящего текста (banned / placeholders).  
4. Persist evidence / claim op_id (после аудита хранилища, без формальной новой БД «ради галочки»).  
5. Staging-прогон QA `docs/qa/client-ai-error-scenarios.md` (после merge docs #262).  
6. Обновление описания PR и ручной merge по согласованию Стратега.

## 5. Команды прогона (канон для этой волны)

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_deception_accusation_policy.py `
  tests/unit/test_deception_evidence_contract.py `
  tests/unit/test_deception_client_reply_policy.py `
  tests/unit/test_deception_transition_refine.py `
  tests/unit/test_deception_negative_guards.py `
  tests/unit/test_multi_intent_policy.py `
  tests/unit/test_client_ai_complex_dialogues.py `
  tests/unit/test_transition_contract_policy.py `
  tests/unit/test_complaint_aggression_policy.py `
  tests/unit/test_contradiction_policy.py `
  tests/unit/test_anxiety_dialogue_policy.py `
  tests/unit/test_lost_document_policy.py `
  tests/unit/test_expectation_alignment_policy.py `
  tests/unit/test_refuse_next_stage_policy.py `
  tests/unit/test_price_refuse_policy.py `
  -q --basetemp=tmp/pytest-sfrfr-110-checkpoint
```

| Отчёт | Состав | Результат |
|---|---|---|
| Ранее «152 passed» | узкий срез deception + complex + multi_intent на `f5822dbd` | исторический; не полный PR |
| Checkpoint после negative/fallback | команда выше | **289 passed** (зафиксировать в комментарии PR) |
