# QA: ТЗ-09 этап D — паритет каналов

Чеклист приёмки. SMS/телефонный OTP — вне scope (не публикуем).

**Базовые URL (после DNS cutover):**

| Роль | URL |
|---|---|
| Витрина WP | `https://proverkastaza.ru/` (временно может жить `https://taxi-doroga-dobra.ru/`) |
| Mini-app | `https://proverkastaza.ru/app/` |
| Кабинет | `https://cabinet.proverkastaza.ru/` |
| API | `https://api.proverkastaza.ru/` |

**Предусловия для сценариев 1–5:** тестовый аккаунт MAX; доступ к кабинету (email OTP или MAX OTP); право upload тестового файла без реальных ПДн (пустой PDF/`readme.txt`).

Автопокрытие (unit):

- [x] CTA уведомлений: порядок по `preferred_channel`
- [x] Deep-link кабинет `/cases/{id}`
- [x] Конфликт `max_user_id` → 409
- [x] OpenAPI: representatives + notification-links
- [x] Общий словарь статусов (`/meta/status-labels` + `shared/status-labels.json`)

## Ручной E2E (сводка)

| # | Сценарий | Статус | Дата / заметка |
|---|---|---|---|
| 1 | WP → MAX → mini-app → upload → статус | [ ] | |
| 2 | WP → веб → OTP (email/MAX) → то же дело после link | [ ] | |
| 3 | Mini-app → «Открыть в браузере» → тот же `case_id` | [ ] | |
| 4 | Веб → «Продолжить в MAX» (Ещё) → документы видны | [ ] | |
| 5 | `run` из веба ↔ mini-app | [ ] | |
| 6 | Конфликт: второй auth не перехватывает `max_user_id` | [x] unit | |
| 7 | Preferred channel меняет порядок ссылок в уведомлении | [x] unit + смена статуса шлёт MAX/чат дела | |

---

## Сценарий 1 — WP → MAX → mini-app → upload → статус

**Шаги**

1. Открыть витрину → CTA «Начать проверку» / `#kak-rabotat`.
2. Выбрать канал **MAX** → открыть бота / mini-app `/app/`.
3. Создать или открыть дело; убедиться, что виден статус pipeline.
4. Загрузить тестовый файл (не ПДн).
5. Обновить экран: файл в списке документов, статус не «сломан».

**Ожидание:** одно `case_id`; upload успешен; статус читается из API.

**Факт / дата / кто:** _…_

---

## Сценарий 2 — WP → веб → OTP → link с MAX

**Шаги**

1. Витрина → выбрать **веб-кабинет**.
2. Войти OTP (email или MAX-код в кабинете).
3. Создать дело или увидеть пустой список.
4. Из MAX (тот же человек) пройти привязку / `link_token`, если кабинет ещё не связан.
5. Открыть то же дело в кабинете после link.

**Ожидание:** один `case_id` в обоих каналах; конфликт чужого `max_user_id` → 409 (уже unit).

**Факт / дата / кто:** _…_

---

## Сценарий 3 — Mini-app → «Открыть в браузере»

**Шаги**

1. В mini-app открыть дело, запомнить `case_id` (URL/UI).
2. Нажать «Открыть в браузере» / deep-link на `cabinet…/cases/{id}`.
3. Пройти OTP при необходимости.
4. Сверить `case_id` и список документов.

**Ожидание:** тот же `case_id`; документы совпадают после refresh.

**Факт / дата / кто:** _…_

---

## Сценарий 4 — Веб → «Продолжить в MAX»

**Шаги**

1. В кабинете: «Ещё» → «Продолжить в MAX» (или блок канала).
2. Открыть mini-app по deeplink.
3. Проверить, что ранее загруженные в вебе документы видны.

**Ожидание:** handoff без второго дела; документы на месте.

**Факт / дата / кто:** _…_

---

## Сценарий 5 — `run` из веба ↔ mini-app

**Шаги**

1. В одном канале запустить проверку / `run` (если доступно по статусу).
2. В другом канале обновить карточку дела.
3. Сверить findings / статус / подсказки RU-лейблов.

**Ожидание:** одинаковый результат в обоих UI (паритет данных, не пикселей).

**Факт / дата / кто:** _…_

---

## Smoke без UI (curl)

Не закрывает E2E 1–5. Только инфраструктура.

```powershell
curl -fsS https://api.proverkastaza.ru/health
curl -fsS https://api.proverkastaza.ru/api/portal/meta/status-labels
# запасной хост до cutover:
curl -fsS https://api.taxi-doroga-dobra.ru/health
curl -fsS https://api.taxi-doroga-dobra.ru/api/portal/meta/status-labels
```

| Проверка | Статус | Дата / заметка |
|---|---|---|
| `GET /health` (taxi) | [x] | 2026-07-26 — 200 `api.taxi-doroga-dobra.ru` |
| `GET /api/portal/meta/status-labels` (taxi) | [x] | 2026-07-26 — путь с префиксом `/api/portal` |
| Витрина `/` (taxi) | [x] | 2026-07-26 — 200 |
| `/blog/` (taxi) | [x] | 2026-07-26 — 200 |
| `proverkastaza.ru` / `api.proverkastaza.ru` | [ ] | DNS ещё не резолвится (ожидание reg.ru / cutover) |
| E2E 1–5 (браузер + MAX) | [ ] | Нужен тестовый MAX и живой прогон |

---

## Как проверить уведомление

1. В admin сменить `pipeline_status` на `human_review` / `draft_ready`.
2. В чате дела появляется системное сообщение с двумя ссылками.
3. Если MAX привязан — сообщение уходит в бот.
4. Порядок ссылок зависит от «Ещё → канал» в кабинете.

## Связанные документы

- [docs/specs/09-client-channels-parity.md](../specs/09-client-channels-parity.md) §10
- [docs/qa/lead-amocrm-e2e.md](lead-amocrm-e2e.md)
