# Постфильтр `max_llm_reply` (SFRFR-110)

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

| Тип | Примеры маркеров | Поведение без trusted ack |
|---|---|---|
| Completed action | «дата исправлена», «исправлено», «всё исправлено» | блок → safe fallback |
| Limit claim | «результат ограничен», «использование ограничено», «отмечен как…» | блок; allow только `limit_outcome=success` на том же деле/версии |
| Регистрация / возврат / назначение | «претензия зарегистрирована», «возврат выполнен», «ответственный назначен» | блок (ack в срезе 1 нет) |

**Не** превращаются в completed-claim (пропуск):

- предложение: «я могу помочь проверить дату»;
- цитата: «вы написали: „дату исправили“»;
- отрицание / неопределённость: «не буду сообщать, что исправление завершено».

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
