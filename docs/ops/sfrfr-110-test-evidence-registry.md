# Реестр свидетельств тестов SFRFR-110 (без подмены)

Хранить локальный прогон и CI раздельно. Не подменять одно другим.

| Метка | Команда | SHA | Результат | Примечание |
|---|---|---|---|---|
| Изолированный срез E05/F04 (принят) | `.\.venv\Scripts\python.exe -m pytest tests/unit/test_max_e05_f04_wire_path.py tests/unit/test_max_sfrfr110_e05_f04_slice.py -q` | `4f60e930858943ee1b9f50e6224966f5c80470f2` | **25 passed** (заявлено в отчёте среза) | Базовый принятый счётчик до Null-блока |
| Контрольная точка Null/исходы (локально) | та же | `4bb8c0d78bf07c993097e19f668ec341b114beb8` | **28 passed** (локально агентом) | Не независимое ревью; не CI |
| Audit PR (локально) | та же (+ тест enqueue fail≠unknown) | `41d957eb` (+ follow-up commit) | **33 passed** локально (до follow-up links) | Не CI; не подмена 25/28 |
| CI GitHub | Checks на PR | head PR | pending/green/red | Только статус Actions |

## PR #263 описание

В body #263 ранее фигурировало «25 passed». Это соответствует **срезу** `4f60e930`.
Локальные **28 passed** на `4bb8c0d7` — отдельная строка реестра, не замена 25.

## Зависимости

- #261 head: `71f44d81f113ae4760fe32eaf39ce4a3d5d5ab01`
- #263 base: `docs/client-ai-dialogue-quality`
- Audit PR base: ветка #263 `feat/sfrfr-110-max-e05-f04-wire`
