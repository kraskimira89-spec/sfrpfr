# SFRFR-110 — gap-матрица (А–К), 2026-10-24

**Статус задачи:** открыта; **не закрывать** по числу сценариев/unit.  
**Координация:** SFRFR-100 · эпик воронки: SFRFR-82.  
**Канон ошибок в main:** PR #262 merge `eea343e357bfbdd70b4a159b21cf1c03fe7aac61` (head `373e3fc0…`).  
**Политики/сценарии:** PR #261 (открыт, head на момент матрицы `7128b6d4…`, auto-merge OFF).  
**Live MAX / deploy / финансы:** только по отдельному согласованию.

Число JSON-сценариев и `289`/`20` unit **не** равны приёмке контура.

---

## 0. Клиентские пути формирования ответа (инвентарь)

| Путь | Код | Политики deception_* / transition | Сейчас |
|---|---|---|---|
| MAX free-text LLM | `handler` → `llm_chat.reply_to_free_text` | только system prompt bullets | prompt-only |
| MAX rule/bot | `case_chat_bot.try_immediate_rule_reply` | нет вызова политик | обход |
| MAX шаблоны/кнопки/статусы | `handler` / pay-link / invoice notify | частично SFRFR-83 статусы | вне каталога E* |
| Кабинет client chat | `portal` → `try_immediate_rule_reply` / зеркало MAX | нет deception_* | обход |
| Staff → клиент MAX | `admin_portal.send_max_reply_to_client` | нет фильтра E* | обход |
| Уведомления (оплата и др.) | `pay_link`, `max_bot_invoice`, SFRFR-95 | не E*-контракт | отдельно |

Критерий «подключено»: тест handler-входа показывает, что неподтверждённое утверждение **не** уходит клиенту в заявленном канале.

---

## 1. Матрица А–К

| ID | Тема | Состояние | Доказательства / код | Связанные задачи | Критерий «готово» | След. шаг |
|---|---|---|---|---|---|---|
| **А** | Канон #262 ↔ политики #261 | **F04 закрыт в #261** (`7128b6d4`); полный E01–E21 audit не завершён | `deception_client_reply_policy` IMPACT_UNKNOWN без обязательного provisional; «отмечен» только `limit_source` system-ack; тесты F04 | SFRFR-110, канон main #262 | Нет двух правил на одно утверждение; F04+негативы зелёные | Выборочный сверка E01–E21 vs policy (док→код), без раздувания #261 |
| **Б** | Подключение к MAX/кабинету | **срез E05/F04 в библиотеке+unit; handler не вшит** | `max_sfrfr110_bridge.build_e05_f04_outbound`; карта: `sfrfr-110-max-integration-slice-2026-10-24.md` | SFRFR-110, SFRFR-53 | Handler-тест: неподтверждённое утверждение блокируется в каждом заявленном канале | Вшить мост в MAX free-text path (точечный PR) |
| **В** | Доверенные факты | **контракт описан; сквозной путь нет** | `persist_flag_is_trusted` / `limit_source`; не подключено к repo ack | SFRFR-110 | Модель не «разрешает» «исправлено»; чужое дело/старая версия не подходят | Собрать facts из результата операции + case_id/version |
| **Г** | Исходящий post-filter | **не готово** (есть banned-helpers в unit) | `reply_has_banned_*`, `SAFE_INCOMPLETE_FACTS_FALLBACK`; не в send-path | SFRFR-110, SFRFR-83 (статусы) | Блок → safe reply; нет ложного успеха и нет молчания | Общий filter перед `append_bot` / LLM send |
| **Д** | Долговременные доказательства | **не подтверждено** | Логическая `evidence_card_*`; `result_evidence` = пенсии; chat log есть | SFRFR-110, gaps doc | Восстановить источник→версию→проверку→исправление; ACL | Аудит store (сообщения/события/docs); gap → только потом storage change |
| **Е** | Жизненный цикл претензии из чата | **библиотека multi_intent; live нет** | `split_deception_compound`, `claim_intake_order`; нет единого API регистрации из чата с номером | SFRFR-110, Tracker STAZH/SFRFR claim ops | Составной запрос не теряет требований; без авто-финансов | Register path: message→save→register≠assign |
| **Ж** | Идемпотентность / unknown | **частично** (message dedupe) | `may_create_duplicate_claim_on_retry=False` (unit); op_id не на всех E* | SFRFR-110 | Повтор ≠ второе действие; сбой → сверка | op_id на register/fix/notify |
| **З** | Последствия / версии | **контракт unit; live нет** | `dual_fix_planes`, `mark_stale_after_error`, needs_recheck | SFRFR-110 | Старое не актуально; один фикс ≠ все зависимости | Addressable needs_recheck + version currency |
| **И** | Notify ≠ read ≠ accept | **контракт unit; live нет** | `notification_transition_order`, may_treat_sent_as_read=False | SFRFR-110, SFRFR-95 | «Исправлено» не закрывает возврат/претензию/пенсию | События prepared/available/sent отдельно |
| **К** | Интеграционная / live приёмка | **не начата** | QA F01–F04 описаны; не гонялись на handler | SFRFR-110, SFRFR-53, отдельный smoke-запрос | Доказательства формирования+сохранения+доставки; live только после ОК | Staging F01–F04; потом запрос live MAX |

---

## 2. Блок А — детали (уже сделано / остаток)

### Сделано (head #261 `7128b6d4`)

- `IMPACT_UNKNOWN`: обязательны `confirmed_point` + `unknown_impact_area`.
- Фразы «отмечен как требующий проверки» / «использование ограничено» — только при `provisional_limit_applied` после trusted `limit_source`.
- Без `limit_source` / LLM-source → неопределённость без фиктивной отметки (F04).
- #262 в `main`; #261 смержен с main; §73 ссылки на канон.

### Остаток А

- Пройти чеклист E01–E21 vs функции reply/transition (таблица «утверждение → функция → тест») без копирования каталога в quality.md.
- Не считать А закрытым для всего E*, только F04/E05-проvisional.

---

## 3. Рекомендуемый порядок (без раздувания #261)

| Блок | Содержание | PR-стратегия |
|---|---|---|
| 1 | А остаток (сверка E*) + закрытие F04 в описании #261 | узкий follow-up в #261 или закрыть А комментарием |
| 2 | **Вертикальный срез:** 1 кейс (рекомендация: E05/F04 или E03 false running) → MAX `reply_to_free_text` path: event → trusted facts → policy → outbound check → reply | **новый PR** от #261/main; не весь каталог |
| 3 | Аудит persist (Д) + op_id (Ж) | отдельный PR / подзадача SFRFR-110 |
| 4 | Последствия/версии (З) + notify (И) | отдельный PR |
| 5 | Кабинет + остальные E* (Б расширение) | после среза; учесть SFRFR-53 |
| 6 | Staging F01–F04 + запрос live smoke (К) | только после согласования |

Новые Tracker-issues создавать **только** если нет покрывающей (сначала SFRFR-110 / 83 / 53).

---

## 4. Условия закрытия SFRFR-110 (напоминание)

Закрывать только при явном согласованном объёме + Б–К по заявленным каналам + критические утверждения из system events + persist/versions/retries + раздельные контуры претензия/финансы/пенсия + интеграционные сценарии + принятые expert/live.  
Вынос требований за 110 — только явным пересмотром объёма и связанными задачами.

---

## 5. Что не делать сейчас

- Merge #261 без новой приёмки Стратега.
- Deploy / live MAX / авто-возвраты / смена хранения «ради галочки».
- Объявлять контур принятым по library unit.
