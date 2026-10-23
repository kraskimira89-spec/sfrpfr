# Этап 1: тесты 1–28 (SFRFR-97)

## Таблица номер → покрытие (до дописывания)

| № | Канон (дизайн) | Файл / тест | Было |
|---|----------------|-------------|------|
| 1 | canceled, нет чека → create | `test_process_posts_after_mark` | есть |
| 2 | canceled + succeeded → gate skip | `test_process_gate_before_create` | есть |
| 3 | reg=pending → skip_pending | `test_process_skip_pending_no_create` | есть |
| 4 | reg пустой → skip_reg | `test_fiscal_reconcile_canon` | **добавлен** |
| 5 | два тика / lease | `test_lease_busy` | есть |
| 6 | окно + ALERT_SINCE без backfill | `test_fiscal_reconcile_queries` | есть |
| 7 | list fail → без +1, streak+1 | canon | **добавлен** |
| 8 | attempts≥3 → нет create + alert; unknown+TTL жив — нет | job + canon | **дописан** |
| 9 | 5xx/timeout → unknown, same key | classify + canon | **дописан** |
| 10 | canceled outcome → +1 новый ключ | canon | **добавлен** |
| 11 | повторный алерт не уходит | claim×2 canon | **добавлен** |
| 12 | unknown + gate succeeded → payload NULL | canon | **добавлен** |
| 13 | TTL истёк + list пуст → +1 | canon | **добавлен** |
| 14 | post_started + TTL жив → без +1 | canon | **добавлен** |
| 15 | lease не двигает post_at | `test_dry_run_only_lease` | есть |
| 16 | CLI reset alerted+attempts | canon (repo method) | **добавлен** |
| 17 | gate fail, TTL жив → без +1 | =7 | есть в 7 |
| 18 | post_at NULL → WARNING TTL-истёк | canon | **добавлен** |
| 19 | ключ >64 → skip | `test_post_rejects` / create phase | есть |
| 20 | gate fail, TTL истёк → без +1 | =7 | есть |
| 21 | HTTP 400 → rejected | classify + canon | **дописан** |
| 22 | snapshot sort_keys | `test_stable_snapshot_sort_keys` | есть |
| 23 | снимок NULL после succeeded | canon | **добавлен** |
| 24 | ALERT_SINCE без backfill | queries | есть |
| 25 | fiscal NULL в предфильтре | queries + not_required | есть |
| 26 | dry-run только lease | `test_dry_run_only_lease` | есть |
| 27 | 3× fetch fail → attempts не 3 | canon | **добавлен** |
| 28 | streak≥12 alert, attempts=0 | job + canon | **дописан** |

Дополнительно по ТЗ: два `or` MockTransport, пустой chat, 2xx non-JSON, garbage ALERT_SINCE → error без list, ENABLED=1 settings.

## Проверки

`pytest tests/unit -k "fiscal or yookassa"` → см. коммит / CI.
