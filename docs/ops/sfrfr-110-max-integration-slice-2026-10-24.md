# SFRFR-110: MAX-интеграция — карта + срез E05/F04 (2026-10-24)

**Не** «весь MAX готов». Результат: один доказанный сквозной путь в **изолированных тестах** + карта обходов.  
Prod send / migrate / deploy — нет. PR #261, auto-merge OFF.

Канон: `client-ai-error-response-catalog.md` (E05), QA F04.  
Код среза: `max_sfrfr110_bridge.py`, охрана outbox: `max_outbox_guards.py`.  
Тесты: `tests/unit/test_max_sfrfr110_e05_f04_slice.py`.

---

## 1. Входной handler (карта; полный аудит webhook — след. шаг)

| Вход | Где (ориентир) | Политики 110 |
|---|---|---|
| Текст | `handler` → `llm_chat.reply_to_free_text` | **пока prompt-only**; мост E05 готов к вызову |
| Callback | `handler` (кнопки) | не подключено |
| Файл | `handler` + file accept texts в `case_chat_delivery` | не E* |
| Служебное | notify / channel_review | не путать с клиентским текстом |

Ограничения: `case_id` из текста ≠ доступ; повтор события ≠ повтор действия; документ не управляет политикой.

---

## 2. Все пути исходящих сообщений

| Путь | Outbox? | Прямой send? |
|---|---|---|
| `enqueue_max_delivery` → `process_pending_outbox` | да | нет (норма) |
| `mirror_client_message_to_max` | да | нет |
| `mirror_staff_message_to_max` | да + **fallback direct** | да при fail enqueue |
| `notify_client_new_chat_message` | нет | **direct** |
| `llm_chat.reply_to_free_text` | нет | **direct** `bot.send_message` |
| `channel_review` | нет | direct |
| pay_link / invoice notify | смешанно | да |
| CLI `send_message` | нет | direct |

`direct_send_bypasses_outbox()` в `max_outbox_guards` — перечень для регрессии.

---

## 3. Место вызова политики (срез)

```text
TrustedOpResult (case_id, operation_id, op_kind, ok, source, version)
→ build_e05_f04_outbound
→ OutboundPackage { text, policy_version, evidence_refs, blocked_reason }
→ (будущее) case_messages + enqueue_max_delivery
→ process_pending_outbox + pre_send_still_allowed
→ MaxBotClient.send_message
→ classify_send_persist_outcome
```

**Сейчас:** вызов из live handler **ещё не вшит** — только библиотека + unit-срез.  
Следующий точечный PR: один call-site в MAX free-text path после сборки trusted ops (не LLM flags).

---

## 4. Источник доверенных фактов

| Утверждение | Основание в срезе |
|---|---|
| Последствия неизвестны | `confirmed_point` + `unknown_impact_area` (контекст дела) |
| Результат ограничен / отмечен | только `TrustedOpResult.trusted_ok_for(case_id)` + source ∈ system-ack |
| «Исправлено» | не генерируется срезом E05 |

Имя `db_write_ack` недостаточно без `case_id` / `operation_id` / `ok` от реальной операции.  
LLM/`llm_self_report` / чужой `case_id` → мера не применена.

---

## 5. Проверка текста и кнопок

- `validate_outbound_client_text` — placeholders, internal labels, длина до truncate.
- Критические ответы E05 — **шаблон политики**, не свободная генерация.
- `invented_model_text` с «ограничено/исправлено» → `blocked_reason`, клиенту — текст без фиктивных утверждений.
- Re-enqueue: `reenqueue_attachments_safe` — нельзя навесить новые кнопки на другой body.

---

## 6. Хранение ответа и доказательств

Срез возвращает `evidence_refs` / `operation_id` / `policy_version` в пакете.  
Долговременный persist связей в БД **не** добавлен (без миграции).  
Существующие: `case_messages`, `case_chat_outbox` — аудит полей для связи op_id — следующий блок.

---

## 7. Идентификатор операции

Обязателен в `OutboundPackage.operation_id` и в `TrustedOpResult.operation_id`.  
Идемпотентность register/fix на полном наборе E* — ещё gap.

---

## 8. Outbox / прямые send

См. §2. Staff mirror: при неуспехе process после enqueue — **не** дублирует, если outbox есть; иначе direct fallback.  
Notify и LLM — вне outbox.

---

## 9. Семантика sent / delivered

`delivered_at_means()`:

- после возврата `send_message` (HTTP ok), **не** read receipt;
- **не** прочтение / приёмка клиентом.

`MaxBotClient.send_message`: `raise_for_status` + JSON; delivery/read не проверяются.

---

## 10. Неизвестный исход

`classify_send_persist_outcome`:

| transport | outbox saved | case_messages | исход |
|---|---|---|---|
| no | * | * | failed |
| yes | no | * | **unknown_after_transport_accept** |
| yes | yes | no | partial_case_message_update |
| yes | yes | yes | sent_and_recorded |

`may_blind_retry_after_unknown_accept() = False`.

Конкуренция воркеров: в `process_pending_outbox` нет atomic claim → `concurrent_claim_required_for_outbox_workers() = True`.

---

## 11. Интеграционные тесты (изолированные)

Файл `test_max_sfrfr110_e05_f04_slice.py`:

- F04: limit fail / LLM source / wrong case → нет «ограничено»
- limit ok + system-ack → можно «отмечен/ограничено»
- model invented claim → blocked_reason + безопасный текст
- mock outbox + unknown after accept → no blind retry
- reenqueue attachments vs body
- offer refused after enqueue → pre-send block

**Не** гонялись: реальный webhook, прод MAX, кабинет end-to-end.

---

## 12. Оставшиеся пробелы

1. Вшить `build_e05_f04_outbound` (и общий контракт) в handler/llm path.  
2. Pre-send hook внутри `process_pending_outbox`.  
3. Atomic claim outbox / конкурентный тест.  
4. Согласованность text+attachments при re-enqueue в прод-коде.  
5. Persist evidence links; claim lifecycle из чата.  
6. Остальные E* + кабинет; staging F01–F04; live smoke — отдельно.

---

## Команда прогона

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_max_sfrfr110_e05_f04_slice.py -q --basetemp=tmp/pytest-e05-f04
```
