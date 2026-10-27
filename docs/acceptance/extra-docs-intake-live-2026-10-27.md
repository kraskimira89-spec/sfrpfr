# Живой прогон: доп. документы anytime + IMAP

**Дата:** 2026-10-27  
**Опубликованный SHA (main / VPS):** `8c162565` (squash merge PR #342)  
**Дело:** тестовое `is_test=true`, prefix `1322ee50` (без ПДн)

## Планировщик

| Параметр | Значение |
|---|---|
| Unit | `sfrfr-mail-inbound-docs.timer` |
| Состояние | **enabled / active (waiting)** |
| Период | каждые 10 мин (`OnUnitActiveSec=10min`) |
| Последний запуск service | `2026-10-27 13:26:54 MSK`, exit 0 |
| Вывод опроса | `{"ok": true, "processed": 0, "detail": "empty_inbox"}` |
| Мониторинг | `/opt/sfrfr/storage/mail_inbound_processed/last_success.json` — `at=2026-10-27T10:26:54Z` |
| Параллельный запуск | file lock в `poll_inbound_mail_documents.py` |

## Результаты проверок ТЗ

| # | Проверка | Результат |
|---|---|---|
| 1 | Кабинет: документ «дети» → статус **Получен** | ✅ `review_status=received` |
| 2 | Чат (MAX upload path) → тот же реестр | ✅ doc в `list_documents`, source=max |
| 3 | Письмо с 2 вложениями + повтор без дублей | ✅ saved=2, повтор `already_processed` / deduped |
| 4 | Неоднозначное письмо → очередь → bind → 2 файла в деле | ✅ blobs_saved=2, bind_saved=2 |
| 5 | **Нужно уточнение** → **Проверен** | ✅ status=checked |
| 6 | **Нужно обновить разбор** без сброса оплаты/согласований | ✅ `b2c_status` остался `service_paid`, pipeline без изменений; задача создана |
| 7 | Изоляция чужого дела + отказ `evil.exe` | ✅ |

`all_ok`: **true**

## Честность метода

Прогон выполнен **на VPS** через те же сервисные функции, что вызывают кабинет / MAX / IMAP (`store_document`, `upload_max_document`, `process_inbound_mail_message`, `bind_unbound_mail_to_case`). Браузерный клик по кнопке кабинета в этой сессии отдельно не снимался — UI-блок «Добавить документ» / mailto задеплоен в `apps/cabinet` на том же SHA.

Этап 5 маршрута **не переоткрывался**.
