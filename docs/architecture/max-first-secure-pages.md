# Архитектура: MAX-first + защищённые страницы действия

**Статус:** Sprint 1–2 done (флаги OFF); upload UI / FSM cutover — Sprint 3–4  
**Дата:** 2026-08-25  
**Стратегия:** до сделки кабинет как «продукт с регистрацией» не нужен; после оплаты — одноразовые защищённые страницы из MAX (не регистрация).  
**Кабинет (`apps/cabinet`) не удаляем** — остаётся полноценным контуром и запасным путём.

Связанные ТЗ: [03](../specs/03-client-cabinet.md), [09](../specs/09-client-channels-parity.md), [20](../specs/20-max-private-chat-funnel.md), [24](../specs/24-max-client-boundaries-home.md), [28](../specs/28-diagnosis-secure-delivery.md).  
Трекер: [SFRFR-23](https://tracker.yandex.ru/SFRFR-23).  
Позиция подачи: [`scripts/assets/copy/submission-position.md`](../../scripts/assets/copy/submission-position.md).  
Цены: 3 000 / 5 000 / 8 000 ₽ поэтапно (`src/sfrfr/services/public_tariffs.py`).

---

## 1. Цель и UX-принцип

### Цель

Снизить трение до оплаты: клиент живёт в **личном чате MAX**. Тяжёлые действия с ПДн (согласие, загрузка, просмотр PDF, оплата по счёту) открываются **короткоживущей защищённой страницей** по ссылке из MAX — без обязательной регистрации и без постоянного «личного кабинета» как первого шага.

### UX-принцип

| Роль поверхности | Что делает клиент | Чего нет |
|---|---|---|
| **MAX = приёмная** | Диагностика кнопками, статус, оплата по ссылке ЮKassa, вызов специалиста | Сканы, СНИЛС, ИЛС в чате |
| **Secure page = действие** | Одно действие: consent / upload / view PDF / pay confirm | Регистрация, список всех дел, пароль |
| **Cabinet = полный контур** | Повторные визиты, история, несколько дел, staff-linked клиенты | Не обязателен до оплаты |

Копирайт и границы:

- сервис **не подаёт** в СФР/Госуслуги вместо клиента;
- **не обещаем** перерасчёт и сумму выплат;
- документы **не принимаем** в чат MAX (уже в prod).

---

## 2. Что уже есть в репо

| Компонент | Статус | Путь / заметка |
|---|---|---|
| Личный чат MAX (intake FSM) | ✅ Есть | `src/sfrfr/integrations/max/handler.py`, `intake.py`; ТЗ-20 |
| Запрет вложений в MAX (prod) | ✅ Есть | `handler.py` + `upload_blocked_keyboard` → CTA кабинета |
| Mini-app / кабинет URL | ✅ Есть | `MAX_MINIAPP_URL`, `CABINET_PUBLIC_URL` (`.env.example`) |
| Веб-кабинет клиента | ✅ Есть | `apps/cabinet` → JWT → `/api/portal` |
| Admin-кабинет | ✅ Есть | `apps/admin` |
| Вход OTP (email) | ✅ Есть | Supabase `signInWithOtp` / `verifyOtp` в cabinet |
| Pair-code MAX ↔ сайт | ✅ Есть | `login_pending.py`, `_handle_pair_code` |
| Magic link / `token_hash` | ✅ Есть (для Auth) | `admin.generate_link(magiclink)` в MAX handler / portal; сессия Supabase, **не** action-page |
| HMAC `max_link_token` | ✅ Есть | `security/max_link_token.py` (TTL 7д, связка MAX→web) |
| initData WebApp | ✅ Есть (MVP) | `security/max_webapp.py` |
| Загрузка документов | ✅ Есть | Portal upload → private Storage; signed URL |
| Consent ПДн до upload | ✅ Есть | Таблица `consents`; `REQUIRE_CONSENT`; `_require_consent_for_upload` |
| Marketing consent | ✅ Есть | `marketing_consents` + сервис гейта promo |
| Тарифы 3/5/8 тыс. | ✅ Есть | `public_tariffs.py` (DIAG 3000, DOCS 5000, SUPPORT 8000) |
| Заказы / платежи | ✅ Есть | `orders`, `payments`; admin + cabinet pay |
| ЮKassa create + webhook | ✅ Есть | `api/routes/payments.py` → `/yookassa/webhook` |
| Notify после оплаты | ✅ Есть | `integrations/payments/notify.py` |
| Secure share PDF диагностики | ✅ Есть (узкий) | `secure_share_links` + `/api/portal/diag-share/{token}` (ТЗ-28) |
| max_intake | ✅ Есть | migration `20260804120000_max_intake.sql` |
| Feature flags MAX-first | ✅ Sprint 1 | `config.py` + `.env.example`: `MAX_FIRST_*` / `SECURE_*` default off |
| Универсальные action links (purpose) | ✅ Sprint 1–2 | `secure_action_links` + `src/sfrfr/secure_links/` |
| Secure page UI (без полной сессии) | ✅ Sprint 2 | `/api/portal/secure/{token}` HTML+JSON (consent, view_pdf) |
| Оплата **до** кабинета как единственный путь | ⚠️ Частично | Счета и pay_url есть; воронка ТЗ-20 всё ещё ведёт в кабинет за документами |

### Сверка утверждений ТЗ с кодом

| Утверждение | Вердикт |
|---|---|
| Уже есть magic links / token_hash? | **Да**, для Supabase Auth (вход в кабинет), не как generic secure action token |
| Как вход в cabinet? | Email OTP / password; MAX pair-code → OTP в чат → approve `token_hash`; mini-app через initData / link_token |
| Где принимаются документы? | Только portal/cabinet (после consent), private bucket |
| Запрет загрузки в MAX? | **Да**, в production отказ + CTA |
| Consent модели? | `consents` (ПДн), contract acceptances, `marketing_consents` |
| Payment webhooks? | **Да**, ЮKassa webhook → `apply_provider_payment` |

---

## 3. Gaps относительно целевого MAX-first

1. **Есть модель** `secure_action_links` (purpose, TTL, max_uses, revoke) — **за флагом OFF**; UI и выдача из MAX ещё нет.
2. **Нет UI «страница одного действия»** (consent-only, upload-only, pdf-viewer-only) — клиент попадает в полный кабинет.
3. **Воронка MAX до оплаты** всё ещё объясняет кабинет как место загрузки (ТЗ-20/24) — нужно переписать сценарии состояний под «сначала оплата / согласие по secure link».
4. **`secure_share_links` жёстко привязан** к `diagnostic_result_id` — не ломаем; общая таблица `secure_action_links` рядом (adapter позже).
5. **`max_link_token`** идентифицирует пользователя MAX на 7 дней, но **не** ограничивает purpose и не аудитит одно действие.
6. **Feature flags** есть, default off — prod auth не меняется.
7. **Паритет mini-app** (ТЗ-09) vs MAX-first: нужно явно решить, mini-app = thin wrapper над secure pages или остаётся полным кабинетом.
8. **Повторный доступ** после истечения ссылки: сейчас логичный путь — снова кабинет/OTP; для MAX-first нужен «запросить новую ссылку в чате».

---

## 4. Целевая схема (текст)

```text
[Сайт CTA] → [Личный чат MAX]
                 │
                 ├─ до оплаты: кнопки, FAQ, специалист, ссылка ЮKassa
                 │              (сканы отклоняются)
                 │
                 ├─ оплата succeeded (webhook) → notify в MAX
                 │         │
                 │         └─ secure link purpose=consent|upload|…
                 │                    │
                 │                    ▼
                 │         [Secure page на cabinet.* или api redirect]
                 │           • проверка token_hash (БД)
                 │           • TTL / max_uses / revoked
                 │           • одно действие + audit
                 │           • без регистрации (опц. короткая cookie сессии действия)
                 │
                 └─ полный cabinet (JWT) — по желанию / повторные визиты / staff

Параллельно остаётся:
  diag-share (ТЗ-28) ⊂ семейства secure links
  admin + ops MAX без изменения модели ПДн
```

---

## 5. Модель secure links (дизайн, не код)

### Сущность (рабочее имя `secure_action_links`)

| Поле | Смысл |
|---|---|
| `id` | UUID |
| `token_hash` | SHA-256 сырого токена; в URL только raw, в БД только hash |
| `purpose` | `consent` \| `upload` \| `view_pdf` \| `pay` \| `diag_share` \| … |
| `case_id` | обязателен |
| `resource_id` | опц.: `order_id` / `document_id` / `diagnostic_result_id` |
| `max_user_id` | опц. привязка к MAX (сверка при открытии из чата) |
| `expires_at` | TTL (например 1–72 ч в зависимости от purpose) |
| `max_uses` / `use_count` | лимит открытий/успешных действий |
| `revoked_at` | ручной и авто revoke |
| `consumed_at` | для одноразовых purpose |
| `created_by` | `system` / staff / bot |
| `meta` | jsonb без ПДн (channel, template_version) |

### Правила

- Сырой токен ≥ 256 bit (`token_urlsafe`); в логах — только prefix.
- В URL **нет** СНИЛС, case number в открытом виде по возможности; `case_id` лучше не светить в query, если достаточно token.
- Prefetch/боты не должны «съедать» одноразовый use (как в diag-share).
- Revoke: при новой ссылке того же purpose, при `do_not_contact`, при смене статуса дела.
- После успешного действия — либо consume, либо уменьшить remaining uses; аудировать в `case` audit / finance_audit по типу.

### Связь с существующим

- **ТЗ-28 `secure_share_links`:** либо миграция в общую таблицу с `purpose=diag_share`, либо thin adapter; не ломать `/diag-share/{token}`.
- **Supabase magiclink `token_hash`:** другой контур (Auth). Не смешивать имена в API.

---

## 6. Состояния MAX-воронки

### До оплаты

| Состояние | MAX показывает | Secure page |
|---|---|---|
| `new` / intake | Цели, ИЛС/трудовая без ПДн | нет |
| `qualified` | Резюме + цена шага 1 (3 000) + pay_url | нет (или `purpose=pay` только как обёртка QR) |
| `awaiting_payment` | Напоминание, специалист | нет документов |
| `attachment_blocked` | Отказ + «после оплаты откроем безопасную страницу» | нет |

### После оплаты

| Состояние | MAX | Secure page |
|---|---|---|
| `paid_need_consent` | Ссылка «Подтвердить согласие» | `purpose=consent` |
| `paid_need_docs` | Ссылка «Загрузить документы» | `purpose=upload` |
| `in_review` | Статус без сканов | — |
| `result_ready` | Ссылка на PDF (как ТЗ-28) | `purpose=view_pdf` / diag_share |
| `need_next_step_pay` | Счёт 5 000 / 8 000 | `purpose=pay` или ЮKassa URL |

Полный cabinet доступен параллельно; MAX-first **не удаляет** `/cabinet` и OTP.

---

## 7. Feature flags (имена)

Предлагаемые переменные (в `.env.example`, default **off**):

| Flag | Default | Смысл |
|---|---|---|
| `MAX_FIRST_FUNNEL_ENABLED` | `0` | Новые тексты/кнопки MAX: оплата до кабинета |
| `SECURE_ACTION_LINKS_ENABLED` | `0` | Выдача/проверка generic action links |
| `SECURE_UPLOAD_ENABLED` | `0` | Upload без полной JWT-сессии (Sprint 3) |
| `SECURE_RESULT_VIEW_ENABLED` | `0` | View PDF / result по токену (Sprint 2) |
| `MAX_SECURE_LINK_BUTTONS_ENABLED` | `0` | Кнопки secure link в MAX-боте |
| `MAX_PAY_LINK_AUTO_SEND` | `0` | После черновика счёта: ЮKassa + кнопка/QR в MAX |
| `SECURE_LINK_PEPPER` | пусто | HMAC pepper; fallback `APP_SECRET_KEY` |

Заготовки под будущие спринты; на prod не включать без staging.  
Существующие релевантные: `REQUIRE_CONSENT`, `MAX_LLM_CHAT_ENABLED`, URL’ы MAX/cabinet.  
Не трогать prod auth при выключенных флагах.

---

## 8. Дорожная карта спринтов 1–4

### Sprint 1 — фундамент (флаги + модель + документация) ✅ done

**Сделано:**

- флаги в `src/sfrfr/core/config.py` + `.env.example` (все default off);
- миграция `supabase/migrations/20260825140000_secure_action_links.sql` (`secure_action_links`, `secure_action_events`);
- пакет `src/sfrfr/secure_links/` (token HMAC, repository, service create/verify/revoke/supersede);
- unit-тесты `tests/unit/test_secure_action_links.py`;
- **не** переключали MAX UX, **не** трогали `/diag-share`, cabinet OTP, UI `/secure/[token]`.

**Готово когда:**

- [x] флаги читаются, default off;
- [x] create→verify→revoke в тестах;
- [x] diag-share и cabinet OTP без регрессии (не менялись);
- [x] этот документ актуален.

История: `docs/history/2026-08-25-max-first-sprint1-secure-links.md`.

### Sprint 2 — consent + view PDF по ссылке ✅ done

**Сделано:**

- HTML/JSON: `GET /api/portal/secure/{token}` (`purpose=consent|view_pdf`);
- `POST /api/portal/secure/{token}/consent` — согласие ПДн без регистрации;
- `GET /api/portal/secure/{token}/pdf` — signed URL (нужен `SECURE_RESULT_VIEW_ENABLED`);
- staff: `POST /api/portal/admin/cases/{id}/secure-links`;
- payment notify: при `MAX_SECURE_LINK_BUTTONS_ENABLED=1` кнопка «Подтвердить согласие»;
- unit-тесты `tests/unit/test_secure_actions_sprint2.py`;
- **не** делали upload UI и cutover MAX FSM.

**Готово когда:**

- [x] клиент без регистрации принимает ПДн-согласие по ссылке;
- [x] PDF по токену (за флагом result view);
- [x] audit через `secure_action_events` + case audit;
- [x] флаги default off — prod без изменений.

История: `docs/history/2026-08-25-max-first-sprint2-consent-pdf.md`.

### Sprint 3 — upload по ссылке

**Делать:** upload-only UI; те же лимиты типов/размера, что portal; revoke после комплекта.  
**Готово когда:** сканы не в MAX; upload только по valid link + consent; Storage private.

### Sprint 4 — MAX states + pay messaging + hardening

**Делать:** FSM до/после оплаты; тексты без обещания перерасчёта; rollback-runbook; метрики; опционально thin mini-app.  
**Готово когда:** E2E: сайт→MAX→pay webhook→secure consent→upload→staff видит документы; выключенные флаги = старое поведение.

---

## 9. Риски и rollback

| Риск | Митигация | Rollback |
|---|---|---|
| Слом prod OTP / pair-code | Не менять login_pending в Sprint 1–2 без флага | Flags off |
| Утечка action token | Только hash в БД; короткий TTL; revoke | Revoke all by case |
| Путаница magiclink vs action token | Разные таблицы/префиксы URL (`/a/{token}` vs Auth) | — |
| Клиент ждёт кабинет «как раньше» | Сохранить CTA «полный кабинет» в меню `/cabinet` | Copy rollback |
| Двойная оплата / гонки webhook | Идемпотентный `apply_provider_payment` (уже есть) | — |
| Мини-апп vs secure page | Явное решение в Sprint 4; не дублировать upload | Flag |

---

## 10. Открытые вопросы

1. Secure pages хостить на `cabinet.proverkastaza.ru` или отдельном path API/WP?
2. Нужна ли короткая httpOnly cookie на время действия или достаточно bearer token в URL + POST?
3. Миграция `secure_share_links` → общая таблица или две таблицы + facade?
4. Обязательна ли привязка `max_user_id` на каждую ссылку (анти-форвард)?
5. Mini-app после MAX-first: thin wrapper или полный паритет ТЗ-09?
6. Когда создавать `case` — на первом сообщении, на оплате или на первом consent?
7. Нужен ли email клиента до оплаты (54-ФЗ / чек ЮKassa) без кабинета?
8. Повторная выдача ссылки: только бот, или ещё SMS/email?
9. Что показывать, если ссылка истекла, а дело уже `paid`?
10. Юридически: акцепт оферты на secure page vs текущий contract_acceptance в кабинете — одна версия?
11. *(из кода)* `DEFAULT_PACKAGE_AMOUNT["ACCOMP"]=8000`, при этом публично есть шаг 5 000 (DOCS) — как маппить заказы на шаги 2/3?
12. *(из кода)* `login_pending` in-memory — ок ли для action links (нет: только БД)?
13. Сохранять ли текущий CTA «в кабинет» на сайте до полного cutover?
14. Staff-созданные счета до MAX-first: слать старые cabinet deep-links или новые action links?

---

## 11. Что НЕ делаем сейчас

- Реализацию Sprint 3–4 (upload UI, FSM cutover).
- Удаление или замену `apps/cabinet`.
- Ломку существующего OTP / pair-code / magiclink Auth.
- Приём документов в MAX «временно».
- Обещания перерасчёта / калькулятор выплат в копирайте воронки.
- Коммит секретов; включение флагов на prod без явного go.
- Массовую перепись ТЗ-20/24 в этом коммите — только ссылка на данный план.

---

## История изменений

| Дата | Что |
|---|---|
| 2026-08-25 | Фаза 0: обследование кода + этот план |
| 2026-08-25 | Sprint 1: флаги OFF + миграция + сервис `secure_links` + unit-тесты |
