# P0+P1: чек-лист проверок «Единый чат и путь клиента»

Дата: 2026-09-01. Область: клиентский кабинет + `POST/GET /api/portal/cases/{id}/messages`.

## UI (375 / 768 / 1280 px)

- [ ] Одна кнопка «Открыть этот чат в MAX ↗» — только в шапке правой панели чата.
- [ ] Слева нет дублирующих «Открыть чат MAX»; ссылки «Задать вопрос» ведут на `#case-chat-input`.
- [ ] Hero при `cta=upload`: якорь «Перейти к загрузке документов» → `#documents`.
- [ ] В «Мои документы» (`#documents`) — единственная главная CTA загрузки.
- [ ] Анкета свёрнута в `<details>`, summary «Ответить на 5 коротких вопросов».
- [ ] Empty state чата один при `messages=[]`; при фильтре без совпадений — «В выбранном фильтре сообщений нет».
- [ ] Sticky чат на desktop не перекрывает якоря; `#case-chat`, `#case-chat-input`, `#documents` скроллятся с отступом.

## Статусы документов

- [ ] `required + missing` → красный «Нужно загрузить».
- [ ] `optional` → серый «Можно добавить», кнопка «Добавить, если есть».
- [ ] `if_pension / conditional` без файла → «Пока не требуется».
- [ ] `staff_requested` (bank) → «Нужен по запросу специалиста», красный статус.
- [ ] `awaiting / accepted / reupload` без регрессий.

## API

- [ ] `GET messages`: клиент не видит `[[internal]]` staff-сообщения.
- [ ] `POST messages` (client): запись в `case_messages` + зеркало в MAX при `max_user_id`.
- [ ] Internal staff POST не уходит в MAX.
- [ ] История не дублируется при refresh/polling (нет двойных строк от echo webhook).

## Автотесты

```powershell
.\.venv\Scripts\Activate.ps1
pytest tests/unit/test_client_work_map.py tests/unit/test_portal_messages.py -q
cd apps/cabinet && npm run build
```

## Регрессии

- [ ] `test_docs_and_copy_no_cabinet_only_wording` (CI).
- [ ] Загрузка `bank_statement` без staff request — 403/отказ (как раньше).
- [ ] Staff max-reply (`/admin/cases/{id}/max-reply`) работает без изменений.
