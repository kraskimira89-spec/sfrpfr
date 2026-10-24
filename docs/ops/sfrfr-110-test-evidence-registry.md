# Реестр свидетельств тестов SFRFR-110 (без подмены)

Хранить локальный прогон и CI раздельно. Не подменять одно другим.
Один результат — один точный SHA команды.

| Метка | Команда | SHA запуска | Результат | Примечание |
|---|---|---|---|---|
| Изолированный срез E05/F04 (принят) | pytest wire+slice | `4f60e930858943ee1b9f50e6224966f5c80470f2` | **25 passed** | Не переносить на поздние head |
| Null/исходы (локально) | та же | `4bb8c0d78bf07c993097e19f668ec341b114beb8` | **28 passed** | Не независимое ревью |
| Audit #265 docs (локально) | та же | `1cd078cd102ae625abd8c2e3cf688f39617bfc5c` | **33 passed** | Head PR `263d629b` — только docs после прогона; результат **не** переносится молча на `263d629b` |
| LLM action-claim filter v1 (локально) | filter+wire+slice | `12debb90409e96ea2a4c9b3b242360be5befad71` | **44 passed** | До ужесточения mixed; не CI |
| `12debb90 → ab493aa6` | — | docs only | — | только `sfrfr-110-test-evidence-registry.md` |
| LLM action-claim filter v1.1 mixed (локально) | `pytest tests/unit/test_max_llm_action_claim_filter.py tests/unit/test_max_e05_f04_wire_path.py -q` | `759d01634aab831b1bcb4fea5a98f91477db0360` | **41 passed** | mixed quote/negation/uncertainty; не CI |
| Совместимость #265 | — | оба base `#263` | — | #265 audit и #266 filter **не** включают друг друга |

## Журнал merge (уточнение)

> #264 смержен в интеграционную ветку `feat/sfrfr-110-max-e05-f04-wire`.
> Merge #261/#263/#265 в `main`, deploy, миграции и live MAX не выполнялись.

Вливание #264 в зависимую ветку изменяет состав проверяемого #263;
это отдельный merge в feature-ветку, не разрешение на merge в `main`.

## Зависимости

- #261: `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01`
- #263 base: `docs/client-ai-dialogue-quality`
- Postfilter PR base: `feat/sfrfr-110-max-e05-f04-wire` @ `4363f9f8` (incl. #264)
