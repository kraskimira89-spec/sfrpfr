# Приёмка ступени 11: разбор ответа СФР

**Дата:** 2026-10-27  
**Код:** `case_response_reviews` + `POST …/response-review/*`; Word/почта/Диск по образцу full_analysis

## Критерии

| # | Проверка | Результат |
|---|---|---|
| 1 | Положительный / частичный / отказ / запрос документов / неполный файл | unit: template при `need_more_pages`; структура AI-промпта |
| 2 | ИИ не подменяет содержание предположениями | system prompt + cite; incomplete → запрос уточнения |
| 3 | Сотрудник правит проект; уходит проверенная версия | `status=reviewed` до send-email/yadisk |
| 4 | Повтор не дублирует | idempotency_key на register |
| 5 | Новый ответ — новая строка | list по `created_at desc`, без overwrite |
| 6 | Браузерный проход: 10 → разбор → проверка → отправка → путь | после deploy + миграция (см. ниже) |
| — | Handoff ≠ reviewed | facts: `received` до AI/review |
| — | Срок → только цитата + контроль ступени 10 | `set-deadline-control` → follow-up |
| — | Исход `offer_escalation` без счёта 8 000 ₽ | `invoice_created: false` |

## Unit

```text
pytest tests/unit/test_response_review.py  → 7 passed
npx tsx --test apps/admin/src/lib/case-funnel.test.ts → stage11 PASS (47)
```

## Live (после merge + migrate)

1. Дело с handoff ступени 10.
2. Зарегистрировать файл ответа, связать с подачей.
3. «Разобрать ответ СФР с ИИ» → правки → «Проверено» → превью почты/Диска → отправка.
4. Выбрать путь (документы / ступень 12 / 13 / ожидание).
5. Убедиться: второй register с тем же idempotency_key → `replayed`; новый document_id → вторая строка.
