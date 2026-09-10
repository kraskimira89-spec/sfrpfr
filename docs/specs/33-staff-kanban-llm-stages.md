# ТЗ-33: Kanban этапов воронки + автоперенос карточек

**Статус:** реализовано (v1)  
**Дата:** 2026-09-09 · **Обновлено:** 2026-09-10  
**Для кого:** backend / admin frontend / QA  
**Связано:** [strategy 5/8](../marketing-sales/strategy-llm-tariffs-5000-8000.md) · [04-admin-cabinet](04-admin-cabinet.md) · [26-max-llm-chat](26-max-llm-chat.md) · `sales_board.py` · `cases-registry.tsx`  
**История:** `docs/history/2026-09-09-kanban-llm-stages-tz.md`

---

## 1. Цель

В кабинете сотрудника показать воронку **колонками** (kanban). Карточка дела **переезжает по столбцам автоматически** при смене фактов дела (оплата, документы, выдача диагностики, оферта). LLM в клиентском чате **ведёт клиента по смыслу** к шагам 3/5/8 тыс.; на доске колонка считается **правилами**, а не свободным текстом модели.

Расширить уже существующий board в [`cases-registry.tsx`](../../apps/admin/src/components/cases-registry.tsx) и канон [`sales_board.py`](../../src/sfrfr/services/sales_board.py) — не строить второй канбан с нуля.

---

## 2. Контекст (as-is)

Сейчас колонки упрощённые:

`new → in_touch → docs → payment → delivery → closed → lost`

Маппинг — функция `sales_board_column(...)` от `pipeline_status`, `b2c_status`, `waiting_on`, `finance_attention`.

Не хватает явных этапов **после DIAG** и раздельных колонок оплаты **3k / 5k / 8k**, из‑за чего «Оплата» смешивает разные счета.

---

## 3. Целевые колонки (v1)

| id | Заголовок UI | Смысл |
|----|--------------|--------|
| `new` | Новый лид | Старт MAX / lead, ещё нет комплекта |
| `qualify` | Квалификация | Intake / согласие / уточнение сегмента |
| `docs_collect` | Сбор документов | Ждём ИЛС/трудовую (waiting_on=client) |
| `pay_diag` | Оплата 3 000 | Черновик/счёт DIAG, ждём оплату |
| `diag_work` | Диагностика | DIAG paid, работа эксперта / HITL |
| `diag_done` | Результат выдан | PDF/итог доставлен клиенту |
| `pay_docs` | Оплата 5 000 | Оффер/счёт шага 2 (DOCS) |
| `docs_work` | Подготовка документов | DOCS paid, сборка комплекта |
| `pay_support` | Оплата 8 000 | Оффер/счёт шага 3 (SUPPORT) |
| `support` | Сопровождение | SUPPORT paid / план подачи |
| `delivery` | Подача клиентом | waiting_on=sfr / awaiting_client_submission |
| `closed` | Закрыто | Успешное закрытие |
| `lost` | Отказ | loss_reason заполнен |

На узком экране допускается группировка (например `pay_*` в одну «Оплаты» с бейджем суммы) — но **ключ колонки в API** хранить полным.

---

## 4. Правила автопереноса (источник истины)

### 4.1 Детерминированный движок

Новый модуль (предпочтительно): `src/sfrfr/services/funnel_board.py`

```text
compute_funnel_column(case, orders, work_flags) -> column_id
```

Приоритет (сверху вниз, первое совпадение):

1. `loss_reason` или b2c/pipeline closed+loss → `lost`
2. b2c closed / pipeline completed → `closed`
3. SUPPORT paid или этап сопровождения → `support` / `delivery` по `waiting_on`
4. Открытый счёт SUPPORT (draft/pending/invoice_sent) → `pay_support`
5. DOCS paid и нет SUPPORT → `docs_work`
6. Открытый счёт DOCS → `pay_docs`
7. Диагностика выдана клиенту (`diagnosis_delivered` / ТЗ-30) → `diag_done`
8. DIAG paid → `diag_work`
9. Открытый счёт DIAG → `pay_diag`
10. Ждём файлы клиента → `docs_collect`
11. Intake / lead → `new` или `qualify`
12. Иначе → `qualify` / `in_touch` legacy map

**Запрещено:** менять колонку только из текста LLM («клиент сказал что оплатил»).

### 4.2 Когда пересчитывать

Вызывать `recompute_funnel_column(case_id)` после:

- создания/обновления order / webhook оплаты;
- `accept_contract`;
- publish/approve диагностики (ТЗ-30);
- смены `waiting_on` / `next_action`;
- загрузки документа (если влияет на «ждём комплект»);
- `handed_to_operator` / resume bot.

Писать в дело поле `funnel_column` (или `sales_board_column`) + audit `funnel_column_changed` с `from/to/reason`.

### 4.3 Роль LLM (ограниченно)

LLM **не** пишет колонку напрямую.

Допустимо:

- обновлять `next_action` / подсказку сотруднику (`staff_reply_suggest` уже есть);
- ставить мягкий флаг `llm_suggested_offer` = `DOCS|SUPPORT` после кнопок клиента — **только если** ворота стратегии 5/8 выполнены; дальше счёт создаёт код.

Опционально (v1.1): endpoint `POST .../suggest-column` для staff — модель предлагает колонку, сотрудник подтверждает. В v1 не обязательно.

---

## 5. UI кабинета сотрудника

### 5.1 Board

В `cases-registry` view `board`:

- колонки из §3 (конфиг с сервера: `GET /api/portal/admin/funnel-board/columns`);
- карточка: ФИО (или «Клиент»), код дела `ПС-…`, `next_action`, бейдж тарифа (DIAG/DOCS/SUPPORT), SLA-полоска как сейчас;
- **без ПДн** на карточке (нет СНИЛС, телефона в открытом виде — телефон только в карточке дела);
- клик → открытие дела (как сейчас);
- drag-and-drop в v1 **выкл** или только admin с audit (чтобы не ломать автологику). Если DnD включают — ручной override пишет `funnel_column_manual` до следующего авто-события или до «сбросить ручной».

### 5.2 Фильтры

- очередь staff / expert;
- «только мои»;
- скрыть тестовые;
- фильтр по тарифу/колонке.

### 5.3 Индикаторы

На карточке в `pay_*`: сумма и статус счёта (`draft` / `invoice_sent` / overdue).  
В `diag_work`: «ждёт эксперта» если `waiting_on=staff`.

---

## 6. API

| Метод | Назначение |
|-------|------------|
| `GET /admin/funnel-board` | колонки + карточки (пагинация per column или один payload ≤ N дел) |
| `GET /admin/funnel-board/columns` | метаданные колонок |
| `POST /admin/cases/{id}/funnel-column/recompute` | принудительный пересчёт |
| `PATCH /admin/cases/{id}/funnel-column` | ручной override (admin/expert), body `{column, reason}` |

Сериализация карточки: переиспользовать поля registry + `funnel_column`, `active_tariff`, `order_summary`.

---

## 7. Связь с MAX / bot_owned / тарифами 5–8

После событий из [strategy-llm-tariffs-5000-8000](../marketing-sales/strategy-llm-tariffs-5000-8000.md):

| Событие | Колонка |
|---------|---------|
| Оффер DIAG отправлен | `pay_diag` |
| DIAG paid | `diag_work` |
| PDF выдан | `diag_done` |
| Клиент «Готов к шагу 2» + создан счёт 5k | `pay_docs` |
| DOCS paid | `docs_work` |
| Оффер 8k | `pay_support` |
| SUPPORT paid | `support` |

LLM в чате озвучивает цену и смысл; **создание order + recompute** — сервисный слой (`max_bot_invoice` расширить на DOCS/SUPPORT по воротам).

---

## 8. Ограничения

- Не показывать на доске текст переписки и OCR.
- Не обещать перерасчёт в подписях колонок/карточек.
- amoCRM не поднимать (резерв); staff cabinet = CRM.
- Не ломать текущий table-view registry.
- Тестовые дела (`is_test_case`) — отдельный тумблер, по умолчанию скрыты.

---

## 9. Тесты и приёмка

1. Unit: таблица кейсов (pipeline/b2c/orders) → ожидаемая `funnel_column`.
2. После mock webhook оплаты DIAG колонка `diag_work`.
3. После publish диагностики → `diag_done`.
4. Создание draft DOCS → `pay_docs`; оплата → `docs_work`.
5. UI: board рендерит ≥ 3 колонки с карточками на фикстурах.
6. Health/docs: обновить `docs/specs/README.md`, краткий playbook в `docs/ops/` при необходимости.

Критерий готовности: сотрудник видит, на каком **тарифном** этапе дело, без открытия карточки; карточки едут сами при оплате/выдаче; LLM не может «перетащить» дело в оплату без order.

---

## 10. Вне scope v1

- Полноценный drag между всеми колонками с конфликтами multi-user.
- Автосоздание счетов 5/8 без ворот стратегии.
- Публичный kanban для клиента.
- Замена очередей Tracker.

---

# Приложение: ТЗ одной копипастой для внешнего ассистента

```text
## Техническое задание для кодера / Яндекс-ассистента

### Цель
Расширить kanban в кабинете сотрудника SFRFR: колонки этапов воронки с тарифами 3000/5000/8000 ₽; карточки дел переезжают автоматически по правилам (не по «мнению» LLM). LLM в MAX только ведёт клиента текстом к оферам по воротам.

### Контекст
- Репозиторий: SFRFR, admin app `apps/admin`, API `src/sfrfr`.
- Уже есть упрощённый board: `apps/admin/src/components/cases-registry.tsx`, канон колонок `src/sfrfr/services/sales_board.py`.
- Тарифы: DIAG 3000, DOCS 5000, SUPPORT 8000 — `src/sfrfr/services/public_tariffs.py`.
- Стратегия оферов 5/8: `docs/marketing-sales/strategy-llm-tariffs-5000-8000.md`.
- Полное ТЗ: `docs/specs/33-staff-kanban-llm-stages.md`.

### Шаги
1. Добавить `compute_funnel_column` + поле/аудит `funnel_column` (или расширить `sales_board_column`).
2. Вызывать recompute на оплате, оферте, выдаче диагностики, смене waiting_on.
3. API `GET /admin/funnel-board` (+ columns); опционально PATCH ручного override.
4. UI board: колонки §3 ТЗ-33, карточка без ПДн, клик в дело; DnD в v1 не обязателен.
5. Не давать LLM писать колонку напрямую; кнопки «Готов к шагу 2/3» → код проверяет ворота → order → recompute.
6. Юнит-тесты маппинга колонок + смоук UI/API.

### Ограничения
- Не трогать prod секреты; не включать глобальный MAX_PAY_LINK_AUTO_SEND без нужды.
- Не обещать перерасчёт/подачу за клиента в UI и промптах.
- Не поднимать amo; staff cabinet = CRM.
- Не ломать table-view реестра.
- Не apply terraform / не коммитить .env.

### Критерии готовности
- Карточка после оплаты DIAG оказывается в «Диагностика», после выдачи PDF — в «Результат выдан», после счёта 5000 — в «Оплата 5 000».
- LLM не может перевести дело в pay_* без order.
- Тесты зелёные; краткий отчёт: какие файлы изменены и как проверить вручную в admin.

---
Это техническое задание для выполнения Яндекс-ассистентом.
```
