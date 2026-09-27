# 2026-09-27 — разбор локального WIP из ветки `OnHome`

## Источник

- Ветка `OnHome`, коммит `064028349d7a5f09477d397c0bf608e4acebfd97` (`0640283`):
  `docs/history/onhome-local-wip/` — 17 `git stash` и 2 локальные ветки с домашнего ПК (`D:\SFRPFR`).
- Сравнение с `main` @ `bad00105`.
- Сырые патчи в `main` не переносились. Восстановить: `git show 0640283:docs/history/onhome-local-wip/<файл>`
  (пока коммит доступен на GitHub) или исходные stash на домашнем ПК (не удалялись).

## Итог

Взят один фикс — клиент Supabase без устаревших `timeout`/`verify` у `SyncPostgrestClient`
(`src/sfrfr/db/session.py`: `supabase_client_options()` с общим `httpx.Client`; тест
`tests/unit/test_supabase_httpx_client_options.py`). Остальное уже есть в `main` в более
новом виде, является автоформатированием, черновыми скриптами или откатило бы исправления `main`.

## Решения по патчам

| Патч | Что внутри | Решение | Причина |
|---|---|---|---|
| `branches/0001-chore-sync-repo-state` | `tools/tmp_count_prod_docs.py` — подсчёт документов на проде | отброшен | одноразовый черновой скрипт |
| `branches/0001-upload-consent-once-pdn` | согласие ПДн один раз, загрузка документов MAX, миграция `20260922120000_…` | отброшен | уже в `main` (PR #73/#78/#89, миграция `20260922130000_client_cookie_consent_once.sql`); лишняя миграция задвоила бы схему |
| `stashes/00` disk-folder | склейка импорта в `case_mirror.py` | отброшен | только форматирование |
| `stashes/01` tmp-tools | `tools/tmp_inventory_*`, `tmp_vps_py.sh` | отброшен | одноразовые инвентаризации прода |
| `stashes/02` sfrpfr-sync-all | `session.py` + тест; devcontainer, `docker-compose.test.yml`, `run-targeted-tests.ps1`, `starlette>=1.7.0`, правки schema/payments/ingest, `storage/`, `tmp/` | частично | взят фикс `session.py` + тест; правки `documents_schema`/`case_repository`/`document_ingest_worker` откатывают защиты `main`; devcontainer/WSL-обвязка вне текущего процесса (`.venv` на Windows); `storage/*.json` и `tmp/` — мусор |
| `stashes/03` before-fio-mirror | почти копия 02 | частично | то же, что 02 (фикс `session.py` взят один раз) |
| `stashes/04` cli-format | `cli/main.py` | отброшен | только форматирование |
| `stashes/05` callback-labels | `test_case_chat_log.py`, `storage/max_chat_pending.json` | отброшен | форматирование + runtime-state |
| `stashes/06` pdn-decline | то же, что 05 | отброшен | форматирование + runtime-state |
| `stashes/07` reactivation | `case_reactivation.py` | отброшен | только форматирование |
| `stashes/08` checklist-funnel | `test_max_intake.py` | отброшен | только форматирование |
| `stashes/09` leadmagnet-email-links | `max_bot_funnel.py` + тесты | отброшен | уже в `main` (там новее: подсказки «Начать» / оферта) |
| `stashes/10` upload-consent-once handler | `_ingest_max_file` без silent local | отброшен | уже в `main` |
| `stashes/11` ads-to-max other2 | `max_bot_invoice.py`, `llm_chat.py`, `case-work-map.tsx`, тест | отброшен | уже в `main` |
| `stashes/12` ads-to-max other | handler + воронка | отброшен | уже в `main` |
| `stashes/13` funnel once-consent | воронка + `scripts/_patch_funnel_tests.py` | отброшен | уже в `main`; скрипт-патчер одноразовый |
| `stashes/14` ads-to-max other-chats | воронка, счёт, история `2026-09-22-upload-consent-once.md`, `_patch_funnel_consent_nudge.py` | отброшен | уже в `main` (история тоже есть) |
| `stashes/15` unrelated-after-merge | `max_bot_invoice.py`, `max_kit_status.py`, handler | отброшен | в `main` новая версия `maybe_offer_diag_invoice` (наследование согласия, догрузка `pay_url`) |
| `stashes/16` leadmagnet-qr-links | согласие ПДн/cookies, work_map, ingest, счёт, форматирование PDF-скрипта | отброшен | альтернативная ранняя реализация того, что в `main` сделано иначе и новее |

## На усмотрение владельца

- `starlette>=1.7.0` (из 02): убирает предупреждение `anyio.abc.BlockingPortal` при anyio ≥ 4.15.
  Сейчас в `.venv` starlette 1.3.1 / anyio 4.14.2 — предупреждения нет; обновление зависимости — отдельной задачей.
- Текст в `max_kit_status.py` из 15/16: «согласие на ПДн уже получено при «Начать» — повторно не спрашиваем».
  В `main` короче; менять копирайт — решение владельца.
- Devcontainer / `docker-compose.test.yml` / `run-targeted-tests.ps1` (WSL) — если понадобится запуск тестов в контейнере.

## Решения владельца (2026-09-27)

1. `starlette` — обновить отдельным PR: `starlette>=1.7.0` и `fastapi>=0.133.0` (первая версия
   fastapi без верхней границы на starlette) в `pyproject.toml` и `requirements.txt`.
2. Текст `max_kit_status.py` — оставить как в `main`.
3. Devcontainer / `docker-compose.test.yml` / `run-targeted-tests.ps1` — не нужны, не переносим.

## Проверено

- `pytest tests/unit/test_supabase_httpx_client_options.py` — красный до правки (ImportError), зелёный после.
- Тесты, использующие `sfrfr.db.session` (16 файлов) — 108 passed.
- `ruff check`, `ruff format --check`, `mypy` по затронутым файлам — чисто.
- Секреты: в переносимом нет токенов/ключей/ПДн; в тесте фиктивные URL и ключ.
