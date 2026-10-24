# Постфильтр `max_llm_reply` (SFRFR-110)

## Формулировка покрытия

> Покрыт перечисленный класс утверждений о выполненных действиях в выбранном
> `max_llm_reply`-пути. Универсальная проверка достоверности ответов и защита
> остальных outbound-путей не доказаны.

## Цель

Не допустить отправку **неподтверждённых утверждений о выполненных действиях**
через обычный LLM-путь, включая возврат туда после пустого policy-ответа.

Это **не** универсальная проверка истинности всех ответов и **не** E01-wire.

## Граница

```text
LLM-ответ
→ apply_position_policy
→ merge soft/nudge attachments
→ filter_llm_action_claims (итоговая версия)
→ return max_llm_reply
```

`файл::функция`:  
`integrations/max/llm_chat.py::reply_to_free_text`  
`services/max_llm_action_claim_filter.py::filter_llm_action_claims`

## Срез 1 — какие утверждения покрыты

Версия фильтра: `sfrfr-110-llm-action-claim-v1.1`.

| Тип | Примеры маркеров | Trusted ack в срезе 1 |
|---|---|---|
| DATE_FIXED | «дата исправлена», «исправлено», «всё исправлено» | **нет** (всегда блок) |
| LIMIT_APPLIED | «результат … ограничен», «использование ограничено», «отмечен как…» | только `limit_outcome=success` на **том же** деле и версии |
| CLAIM_REGISTERED / REFUND_DONE / ASSIGNEE_SET | регистрация / возврат / назначение | **нет** |

Ack одного вида **не** разрешает другой (limit ≠ дата ≠ возврат).

Смешанные сообщения: цитата / отрицание / неопределённость в одной части
**не** отключают проверку голого утверждения в другой
(кавычки маскируются; отрицание — только локально перед маркером).

Чистые офферы без маркера completed-action («могу помочь проверить дату») —
не блок. Чистые отрицания без голого claim — не блок.

## Safe fallback

`SAFE_INCOMPLETE_FACTS_FALLBACK` / `ACTION_CLAIM_SAFE_FALLBACK`.  
При блоке — strip `inline_keyboard` / `keyboard`.

При ошибке фильтра — тот же safe text, **не** исходный непроверенный.

## Что не делает этот PR

- запись даты / staff write / миграции;
- новый TrustedOpResult для persist даты;
- защита rule-bot / callback / staff mirror;
- идемпотентность outbox при UNKNOWN_AFTER_ACCEPT.

## Тесты

`tests/unit/test_max_llm_action_claim_filter.py`
