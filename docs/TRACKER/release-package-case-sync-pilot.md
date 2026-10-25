# Пакет выпуска: CASE sync (пилот)

**Дата проверки:** 2026-10-25  
**Владелец со стороны проекта:** Сергей Богдановский  
**Решение по очереди:** вариант **A** — очередь `CASE` (не переименовывать в `DELO`)  
**Задача:** [SFRFR-118](https://tracker.yandex.ru/SFRFR-118)

> Разделяем: **код выпущен** ≠ **интеграция включена**.  
> Сейчас допустим только контур «код на проде, sync выкл.». Включение флага — только после согласования этого пакета и закрытия блокеров ниже.

---

## 0. Коррекция устаревшего отчёта (ассистент / GitHub)

| Утверждение в старом отчёте | Факт на 2026-10-25 ~08:20 UTC |
|---|---|
| PR №281 открыт, не в `main` | **#281 закрыт** (без merge). Рабочий выпуск — **[#282](https://github.com/kraskimira89-spec/sfrpfr/pull/282)** |
| Изменения не на production | **Код на VPS:** `eb17ecb6` (= squash merge #282). `deploy-vps` run `40175831638` — **success** |
| Только срез 1 | В #282: async client, outbox worker (библиотека), inbox→`task_state`, webhook за флагом, DDL, очередь CASE |

---

## 1. Production-контур (проверено)

| Проверка | Результат |
|---|---|
| App commit `/opt/sfrfr` | `eb17ecb6` — `feat(tracker): outbox/inbox проекции + CASE (на прод) (#282)` |
| CI #282 | `api` / `cabinet` / `admin` — **pass** |
| Deploy | `deploy-vps` на `main` — **success** |
| `SUPABASE_URL` | `https://supabase2.proverkastaza.ru` |
| `DATABASE_URL` host | `194.67.116.168:5433` (supabase2) |
| Миграции в **этой** БД | `20261025120000_tracker_sync_outbox.sql`, `20261025130000_tracker_sync_schema.sql` — в `sfrfr_ops.schema_migrations` @ 2026-10-25 07:58 UTC |
| Таблицы | `public.tracker_sync_outbox` + `tracker_sync.{bindings,task_state,inbox,change_history,outbox,delivery_attempts}` |
| `TRACKER_CASE_SYNC_ENABLED` | **отсутствует** в `.env` → default **false** |
| `TRACKER_CASE_QUEUE` / `TRACKER_CASE_FIELD_IDS_JSON` / `TRACKER_WEBHOOK_*` | **отсутствуют** |
| `TRACKER_QUEUE` | `STAZH` (quality; не путать с CASE) |
| Webhook live | `POST :8011/api/integrations/tracker/commands` → **503** `tracker_case_sync_disabled` (ожидаемо) |
| systemd tracker-sync worker | **нет** (есть только `sfrfr-tech-debt` для snapshot STAZH) |

Повторно DDL **не** накатывать: обе миграции уже в реестре этой БД.

---

## 2. Очередь CASE (проверено API)

| Параметр | Значение |
|---|---|
| Ключ | `CASE` |
| Имя | Клиентские дела (диспетчерская) |
| Lead сейчас | `proverkastaza` / uid `8000000000000002` («Проверка Стажа») |
| Карточек в очереди | **0** |
| Локальные поля `case_ref` / `current_stage` / `case_revision` | **не созданы** (`queue_get_fields` без локальных ID) |
| `TRACKER_CASE_FIELD_IDS_JSON` на VPS | не задан |

### Учётная запись владельца (Сергей)

| Tracker uid | login | display | email | dismissed |
|---|---|---|---|---|
| `8000000000000005` | `info` | Сергей Викторович Богдановский | info@proverkastaza.ru | **true** |
| `8000000000000006` | `info` | Стажа работник Проверка | info@proverkastaza.ru | false |

**Блокер:** активной учётной записи «Сергей Богдановский» в org нет (профиль уволен). Не подставлять GitHub-логин. Нужно в UI Трекера: восстановить/создать активный аккаунт Сергея и назначить **lead** очереди `CASE` на его Tracker uid.

Сервисный OAuth (`TRACKER_TOKEN` на VPS) для STAZH уже работает; права на create/update в `CASE` перед пилотом проверить отдельным dry-run create→delete/cancel на тестовой карточке **после** появления локальных полей.

---

## 3. Runtime: что есть в коде и чего нет в проде

| Компонент | Код | Прод |
|---|---|---|
| Async `TrackerClient` | да | загружен с API |
| `process_tracker_outbox` / `process_tracker_inbox` | да (unit-тесты) | **никто не вызывает** (нет unit/timer/cron) |
| Enqueue из бизнес-событий дела | **нет** (нет вызовов из services/routes) | — |
| Postgres store для outbox/inbox | **нет** (только `InMemory*Store`) | webhook пишет в process-local memory |
| Webhook accept | да, за флагом | 503 пока sync выкл. |
| STAZH quality из admin | да | работает как раньше |

**Вывод:** наличие Python-файлов worker ≠ запуск. Сквозной путь app→outbox→CASE→сводка **сейчас неисполним** без доработки wiring + Postgres repository + systemd (или in-process tick).

---

## 4. UI сотрудника (admin)

| Нужно для приёмки | Сейчас |
|---|---|
| Ссылка на **CASE**-карточку дела | Есть только ссылка на задачу Трекера из `tracker_last_issue_key` (**STAZH quality**), не CASE-parent |
| Состояние синхронизации | **нет** |
| Последнее успешное обновление | **нет** |
| Ошибка / ожидание sync | **нет** |

Это **недостающая работа**, не «уже видно в кабинете».

---

## 5. Сквозные сценарии (статус)

| # | Сценарий | Статус |
|---|---|---|
| 5 | Событие app → outbox → одна parent CASE → сводка 13 ступеней; повтор без второй карточки | **не готов** (нет enqueue, worker, field IDs, Postgres store) |
| 6 | Webhook → inbox → рабочий статус; **без** смены оплаты/подачи/ступеней | Код inbox ограничивает команды; на проде sync выкл.; store in-memory — **не готов к пилоту** |
| 7 | Видимость в UI дела | **не готов** |

Клиентские напоминания и массовое создание карточек для старых дел — **вне** этого выпуска (как в ТЗ).

---

## 6. Блокеры до включения `TRACKER_CASE_SYNC_ENABLED=1`

1. Активный Tracker-аккаунт Сергея → lead `CASE`.  
2. Локальные поля CASE + заполненный `TRACKER_CASE_FIELD_IDS_JSON` (без дублей полей).  
3. Postgres repositories для `tracker_sync.outbox` / `inbox` / `bindings` / `task_state` (убрать InMemory из webhook path).  
4. Enqueue из разрешённых фактов дела (без оплаты/подачи из Трекера).  
5. Worker: systemd timer/service **или** безопасный tick в API — с метриками ошибок в лог.  
6. Минимальный admin UI: CASE key/url, sync status, last_ok_at, last_error.  
7. Тест на **одном** тестовом деле + скрин/запись UI (не только SELECT из БД).  
8. Секреты: `TRACKER_WEBHOOK_SECRET`, `TRACKER_WEBHOOK_ORGANIZATION_ID` — только в VPS `.env` / Lockbox, не в git.  
9. Rollback: выставить `TRACKER_CASE_SYNC_ENABLED=0` (+ убрать webhook secret / автодействие в Трекере) без отката DDL.

---

## 7. Порядок включения (после закрытия блокеров и «ок» владельца)

1. Deploy кода wiring (отдельный PR) при **sync=0**.  
2. Smoke: webhook → 503; health API; STAZH quality без регрессии.  
3. Выставить field IDs + webhook secret на VPS; sync всё ещё **0**.  
4. Включить sync **только** для allowlist тестового `case_id` (если нет allowlist в коде — сначала добавить; иначе не включать глобально).  
5. Один сквозной сценарий 5→6→7.  
6. Rollback drill: sync=0, убедиться что факты в БД не менялись из Трекера.

---

## 8. Rollback (без значений секретов)

| Действие | Как |
|---|---|
| Выключить интеграцию | `TRACKER_CASE_SYNC_ENABLED=0` + restart `sfrfr-api` |
| Остановить webhook | удалить/ротация `TRACKER_WEBHOOK_SECRET`; отключить автодействие в Трекере |
| Worker | `systemctl stop` unit (когда появится) |
| DDL | **не откатывать** (таблицы безвредны при sync=0) |
| Карточки CASE | не удалять массово; тестовую можно закрыть вручную |

---

## 9. Решение владельца (нужен явный ответ)

- [ ] Подтвердить пакет: код на `eb17ecb6` с sync=0 — **принято как этап «код выпущен»**.  
- [ ] Восстановить активный Tracker uid Сергея и назначить lead `CASE`.  
- [ ] Разрешить следующий PR: Postgres store + enqueue + worker + минимальный UI (**без** глобального sync).  
- [ ] После зелёного пилота на 1 деле — отдельно согласовать `TRACKER_CASE_SYNC_ENABLED=1`.

**Сейчас флаги на проде не включались и не будут включены без этого согласования.**
