## 2026-07-28 (форма: галочка СОПД)

- Перед отправкой заявки и регистрации — обязательный чекбокс СОПД + ссылка `/soglasie/`.



- Форма заявки: имя (обяз.), email и телефон по желанию, нужен хотя бы один контакт.
- Кабинет `?mode=register`: код на почту или в MAX → ввод на сайте.
- API лида: `email`/`phone`; deep-link в кабинет с префиллом.



- Облако `sfrfr-ai` (`b1gkscu5sqpjtf5d5rbi`), каталог `default` (`b1g0mhpm9tr4lrurk1bu`).
- Биллинг всё ещё 0 ₽ / «Облако заблокировано» — SA/ключ на паузе.

## 2026-07-28 (стоп: Yandex Cloud заблокирован)

- Баннер «Облако заблокировано», баланс 0 ₽ → шаг AI Studio (SA/ключ) на паузе.
- Ops: `docs/ops/yandex-cloud-billing-unblock.md`. Workspace OAuth не затронут.

## 2026-07-28 (промпт AI Studio)

- `prompts/system/yandex-ai-studio-agent.md` — агент LLM / YandexGPT.

## 2026-07-28 (Yandex: org mailbox + employee Telemost)

- Env: блок Workspace дописан в локальный `.env` (раньше только secrets).
- Модель: Диск/Почта/Календарь = `proverkastaza`; Телемост = `info@proverkastaza.ru`.
- Healthcheck: ping/disk/cal/mail/telemost — ok; VPS `.env` ключи на месте.

## 2026-07-28 (Workspace: Диск + календарь)

- Проверка `yandex-workspace-setup.md`: OAuth apps ок, Disk/CalDAV/Telemost/Mail.
- Включён Диск (только SFRFR-ops); дублирование Google Calendar в Яндекс.

## 2026-07-28 (промпты агентов)

- Папка `prompts/system/`; первый промпт — агент Яндекс.Облако.

## 2026-07-28 (ops: self-host Supabase в YC)

- Runbook: `docs/ops/supabase-selfhost-yandex-cloud.md` (ВМ + Docker Compose, TLS, бэкапы, cutover).
- Ссылка из ТЗ-15.

## 2026-07-28 (копирайт каналов)

- После заявки и на лендинге: «Личный кабинет на сайте» / «Открыть кабинет на сайте» вместо «в браузере».

## 2026-07-27 (ТЗ-15 локализация ПДн)

- Рекомендации 152-ФЗ сохранены в `docs/specs/15-data-localization-ru.md`.
- MVP: оставляем Supabase Cloud; целевой — self-host Supabase в Yandex Cloud + SmartCaptcha.
- План миграции фазы 0–4; пояснение Supabase ≠ Yandex Cloud.
- Canvas: `data-localization-options.canvas.tsx`.

## 2026-07-27 (код ТЗ-14 Yandex Workspace)

- Модуль `integrations/yandex_workspace`: ping, Телемост, SMTP XOAUTH2, CalDAV.
- CLI + admin API `/telemost` `/email`; кнопка в admin; миграция `cases.meeting_url`.
- Телемост на личном аккаунте → 403 Organizations (нужен 360).

## 2026-07-27 (ТЗ-14 Яндекс Workspace)

- OAuth ID для `proverkastaza@yandex.ru`: почта, Телемост, календарь; Диск off по умолчанию.
- Файлы: `docs/specs/14-yandex-workspace.md`, `docs/ops/yandex-workspace-setup.md`.

## 2026-07-27 (ТЗ-13 document ingest v2)

- Спека: пороги text layer, артефакты extracted.md/ingest.json, Vision vs Tesseract, HITL сверка в admin.
- Файл: `docs/specs/13-document-ingest-v2.md`.

## 2026-07-27 (код: убран Taganay)

- Удалён `integrations/taganay`; sync только amoCRM (public leads, admin, CLI).
- Admin UI: ссылки «amoCRM»; тест payload без файлов переведён на AmoCrmClient.

## 2026-07-27 (доки: Taganay → amoCRM)

- Во всех ТЗ и docs заменена CRM Taganay на amoCRM; QA-чеклист → `docs/qa/lead-amocrm-e2e.md`.
- Удалён `docs/qa/lead-taganay-e2e.md`; поправлены битые фразы после replace.

## 2026-07-27 (ТЗ-11: дожим P0 + UI)

- Главная: блок 3 статей `#stati`; комментарии закрыты; slug `rodstvenniki`.
- Статьи P0 #5–8, #10–12; related — до 3 ссылок, без насыщения.
- Инструкция: sitemap Rank Math.

## 2026-07-26 (лендинг: меню под короткую воронку)

- Primary: Как это работает / Тарифы / Вопросы / О сервисе / Статьи / CTA.
- Оферта и ПДн — только footer; `wp_apply_landing_vps.sh` для выкладки WP.

## 2026-07-27 (amoCRM: воронка + тест)

- Воронка переименована в «Проверка стажа»; этап «Новый лид» создан (системный «Неразобранное» не редактируется API).
- `AMO_STATUS_ID=87464262`; тестовая сделка `47044633` с CASE_ID.
- Скрипт `scripts/amocrm_rename_pipeline.py`; секреты в `secrets/amocrm.env` + VPS `.env`.

## 2026-07-26 (amoCRM: ответ поддержки)

- План API v4 / приватная интеграция / long-lived token — подтверждён.
- Заявление об отказе и публичная модерация для приватной интеграции не нужны.
- Обновлён `docs/ops/amocrm-setup.md` v1.3.

## 2026-07-26 (amoCRM: ТЗ настройки UI)

- По доке OAuth/custom fields сохранены шаги 0–7: амоМаркет → токен → воронка → поля → VPS.
- Файлы: `docs/ops/amocrm-setup.md`, обновлён `docs/specs/12-amocrm.md`.

## 2026-07-26 (amoCRM)

- Исследование custom fields → ТЗ-12 и модуль sync в коде.
- Env: AMO_SUBDOMAIN / AMO_ACCESS_TOKEN; без токена — skipped.
- Сохранена пошаговая настройка UI: `docs/ops/amocrm-setup.md`.

## 2026-07-26 (лендинг: сжатие + перенос в блог)

- Главная: 8 блоков; hero SVG; один primary CTA MAX; sticky MAX на mobile.
- Убрано в статьи: ситуации, родственники, результат, каналы, расширенный FAQ.
- Сид ТЗ-11: статьи 05–09; тизер `#stati` с главной снят.

## 2026-07-26 (лендинг: закрытие UI-замечаний сверки)

- Тарифы: раскрывающийся пример расчёта (5000×3).
- Блок `#o-servise` — кто оказывает услугу + правила.
- MAX как основной канал; кабинет — дополнительно (live URL).
- Hover кнопок с контрастным текстом; секции ~экран; padding карточек 24px.
- `#zayavka` без двойного `--alt` после статей.

## 2026-07-28 (оглавление Яндекс ID / Вебмастер / Метрика)

- Папки `Yandex ID/`, `Yandex Webmaster/`, `Yandex Metrika/` — по 2 файла (пользователь/разработчик).
- Акцент: OAuth для Workspace; Вебмастер для `proverkastaza.ru`; Метрика без ПДн в целях.

## 2026-07-28 (оглавление Yandex Cloud + AI Studio)

- Папки `Yandex Cloud/` и `Yandex AI Studio/`: по 2 файла (пользователь / разработчик), таблицы ссылка·раздел·кратко·SFRFR.
- Разведены контуры: Cloud инфра/Vision/Captcha vs AI Studio LLM vs Workspace OAuth (ТЗ-14).

## 2026-07-27 (оглавление документации MAX)

- Папка `MAX/`: `01-polzovatelskaya-dokumentaciya.md`, `02-dokumentaciya-razrabotchika.md`.
- Таблицы: ссылка / раздел / кратко / приоритет SFRFR (business/help + API/Bridge).

## 2026-07-27 (оглавление документации amoCRM)

- Папка `amo CRM/`: `01-polzovatelskaya-dokumentaciya.md`, `02-dokumentaciya-razrabotchika.md`.
- Таблицы: ссылка / раздел / кратко / приоритет для SFRFR (без полного текста статей).

## 2026-07-26 (хвосты cutover: MAX / Supabase / reCAPTCHA)

- На VPS уже ок: `MAX_MINIAPP_URL`, `/app/` 200, cabinet/API URL.
- Пользователь закрыл вручную: MAX mini-app URL, reCAPTCHA domains, Supabase redirects (`cabinet.proverkastaza.ru/**` + recover).
- Чеклист: `docs/ops/cutover-manual-checklist.md` — все три ✅.

## 2026-07-26 (fix редиректов prostaz.ru / proverka-staza.ru)

- Симптом: `http://prostaz.ru` → Apache2 Default Page (не 301).
- Причина: certbot закомментировал кросс-доменный RewriteRule и завёл конфликтующие *:80 в `*-le-ssl.conf`.
- На VPS переписаны `redirect-proverkastaza-aliases.conf` + `-le-ssl.conf`; снаружи все алиасы → `https://proverkastaza.ru/`.
- В репо: шаблон `docs/apache-vhost-redirect-aliases-le-ssl.conf`; cutover после certbot ставит чистые конфиги.

## 2026-07-26 (закрытие открытых P0/P1 docs)

- Восстановлен `docs/specs/11-blog.md` (был DISK FULL) + §13 UI; ref `11-blog-ref-entuziastov.md`.
- UI блога: `scripts/assets/blog/ui/` + MU `sfrfr-blog-ui.php` + `wp_deploy_blog_ui.sh`.
- **Деплой:** MU на VPS (`taxi-doroga-dobra.ru/blog/` — чипы/CSS live); хук в `vps_deploy.sh`.
- **Cutover DNS/SSL:** `vps_cutover_proverkastaza.sh` — LE-сертификаты на `proverkastaza.ru` + api/cabinet/admin + алиасы; WP home/siteurl → новый домен.
- ТЗ-09 D: детальный runbook в `docs/qa/tz09-stage-d.md`; E2E 1–5 ещё `[ ]` (нужен MAX).
- Лид→amoCRM: чеклист `docs/qa/lead-amocrm-e2e.md`; POST leads без токена → 401.
- Юрпроверка оферты/success fee и Notion MCP/`np/` — внешние блокеры.
- Вручную: MAX mini-app URL, Supabase redirects, добавить `proverkastaza.ru` в allowlist reCAPTCHA Enterprise.

## 2026-07-26 (выбор и cutover домена)

- Выбран основной `proverkastaza.ru` (не `ptostaz` / без дефиса).
- Куплены также `proverka-staza.ru` и `prostaz.ru` (редиректы).
- В репо: DNS-инструкция, Apache-конфиги, `vps_cutover_proverkastaza.sh`, URL в коде.

## 2026-07-26 (dbt Labs plugin demo)

- Показан плагин: skill analytics engineering → gap analysis → Tier-1 тесты в `schema.yml`.
- `stg_communications` был без YAML; marts без unique/relationships на case_id.

## 2026-07-26 (восстановление чатов после переноса AppData)

- История чатов в UI Cursor после переноса AppData потеряна (не восстановить как UI-сессии).
- Собран читаемый архив содержимого из `agent-transcripts`: `docs/history/recovered-chats-2026-07-26.md`.
- Обработаны только топ-уровневые чаты (без subagents); пустые чаты отмечены отдельно.

## 2026-07-25 (ситуации из DeepSeek → блог)

- Запрос: каждый клиент — статья; каждые 5 — аналитика.
- Сделано 25+5 обезличенных постов; исходные chat summary в блог не копировали.

## 2026-07-25 (блог: URL статей)

- После сида статьи отдавали 404 из‑за `category_base=blog`.
- Исправлено на `blog/rubrika`; live: 4 статьи + `/blog/` = 200.

## 2026-07-25 (ТЗ-11 блог MVP)

- Сид `wp_seed_blog_tz11`: `/blog/`, 4 статьи, рубрики, CTA `#kak-rabotat`.
- Главная: «Читайте также» + ссылки из FAQ; `docs/ops-blog-editor.md`.

## 2026-07-25 (ТЗ блога)

- Сохранено ТЗ блога: `docs/specs/11-blog.md`; индекс в `docs/specs/README.md`.
- Новые ТЗ — только в `docs/specs/`.

## 2026-07-22 (вход admin = паттерн клиента)

- Admin: одна кнопка «Войти через MAX», email над кнопкой, шаги 1–2–3, крупный код.
- Email OTP в «Другие способы»; без вкладок и без саморегистрации.
- Staff: `pending_manager` при первом входе; тексты без лишнего confirm.

## 2026-07-22 (ТЗ-03/09 без SMS)

- Канал и «Продолжить в MAX» в «Ещё»; deep-link `/cases/{id}`.
- Общий словарь статусов (`shared/status-labels.json` + `/meta/status-labels`).
- Уведомления о смене статуса: MAX + системное сообщение с двумя CTA.
- UI/API законного представителя (admin + бейдж в кабинете).
- QA этап D: `docs/qa/tz09-stage-d.md`; SMS OTP не публикуем.

## 2026-07-22 (P0 кабинет для пенсионеров)

- Домашний экран «Сейчас нужно» + шаги 1–2–3 (согласие → документы → проверка).
- Пароль опционально: «Перейти к делу без пароля» (`sessionStorage`).
- Скрыты «Канал работы» и верхние вкладки; Оплаты/Результат/Пароль в «Ещё».
- Вход: запасные способы в `<details>Другие способы</details>`, крупный код/кнопки.
- Пустые findings/чек-лист/черновик не показываются; человеческие статусы.

## 2026-07-25 (MAX: кнопки без дублей)

- Wizard регистрации: одна колонка кнопок (открыть чат → код).
- В MAX после «Начать»: кнопка-ссылка «Получить код в браузере» → `?get_code=1`.

## 2026-07-25 (auth logging → кабинет)

- Структурированные события `sfrfr.auth.portal` (otp_request/poll/verify/link, max_pair/login).
- Фикс `RedactingFilter`: не трогать `uvicorn.access` (иначе ValueError в api.err).
- `_session_from_max_identity` сам создаёт clients при отсутствии строки.
- Юнит-тесты smoke OTP + poll approved; деплой на VPS.
- E2E: pair→approve→session OK; `/me` 500 из‑за `staff_roles.maybe_single` → `limit(1)`.

## 2026-07-25 (fix: связать MAX-аккаунт)

- `maybe_single()` на пустых `clients` ломал создание профиля → «Не удалось связать аккаунт».
- Заменено на `limit(1)`; при создании MAX-клиента сразу auth.users + user_id.

## 2026-07-25 (бренд → главная)

- «Проверка стажа» и логотип — ссылки на сайт с title «На главную»
  (кабинет, admin, лендинг, miniapp).

## 2026-07-25 (автокоммит)

- Правило `.cursor/rules/auto-commit-deploy.mdc`: после каждого задания —
  коммит + push на `main` (деплой) без вопроса; Auto Keep правок.

## 2026-07-25 (P0 упрощение входа)

- CTA сайта → `#kak-rabotat`; браузер → кабинет `?mode=register&channel=max`.
- Кабинет по умолчанию: вкладка «Регистрация» + чат MAX.
- После входа без дел — автосоздание и открытие дела.

## 2026-07-25 (вход после кода)

- После 6-значного кода в чате MAX: сразу авторизация на странице входа;
  кнопки «Работать в приложении» / «Работать в интерфейсе»; без «Начать» и без
  лишней «Подтвердить вход».

## 2026-07-25 (поздно вечером)

- Единые термины на всех шагах входа: **чат MAX**, **браузер**, **страница входа**, **почта**.
- Бот после «Начать» просит кнопку **«Показать код для MAX»** (как на странице входа),
  а не «Получить подтверждение».
- Кнопка в чате MAX: **«Подтвердить вход в браузере»** (вместо «…в веб кабинет»).

## 2026-07-25 (вечер)

- Личный кабинет: меню «Начать проверку» → `#zayavka`; пункт «Личный кабинет»;
  вход email+пароль / MAX / код на email; регистрация с назначением пароля; восстановление.
  Redirect recovery: `https://cabinet.taxi-doroga-dobra.ru/?mode=recover`
  (в Supabase Auth → URL Configuration должен быть allow-list на cabinet.*).
- Синхронизация веб-мастера и MAX: шаг «Начать» ↔ кнопка «Начать»; шаг 3 ↔ код + «Подтвердить вход»; без ложных confirm и ручного `/start`.
- MAX: кнопка «Подтвердить вход в веб кабинет» снова link (`?auth=max&t=`) — открывает браузер; poll на ПК одобряется при открытии ссылки.
- VPS: кабинет не пересобирался при деплое (устаревший UI); `vps_deploy.sh` чинит rebuild Next.js; старый текст «Рекомендуемый вход… / Открыть чат MAX» снят с прода.
- Кабинет клиента: интерактивный мастер входа MAX (3 шага); лендинг/miniapp → кабинет без форса MAX-wizard.

## 2026-07-25 (день)

- Nightly dbt оставлен на VPS: systemd timer в 05:30 МСК и direct PostgreSQL
  endpoint после Supabase IPv4 add-on; внешние GitHub Actions не используются.
- Чистый `dbt build` на VPS: **35/35 PASS**; RLS через `dbt_apply_rls.sh`
  (post-hook в dbt зависал на COMMIT).

## 2026-07-25 (утро)

- Проверка VPS по SSH: хост жив, `DBT_*` и dbt debug OK; `dbt build` через pooler зависает.
- Витрины пересобраны `psql` (staging + marts + RLS); cron dbt отключён до IPv4/direct.

## 2026-07-24 (вечер)

- RLS на витринах `analytics.*` через dbt post-hook; SSH к VPS по-прежнему timeout.
- dbt: Supabase `analytics_source`/`analytics` и роль `analytics_transformer`; `dbt build` — 35/35 PASS. Витрины исключают ПДн и точные суммы.
- Кабинет сотрудника: вход через MAX как у клиента + этап подтверждения руководителем
  (`pending_manager`, кнопка «Разрешить вход сотруднику»).
- Руководитель: `max_user_id=6407832`, `chat_id=321180237` —
  в `staff_roles` (admin taganai89) и `STAFF_LOGIN_APPROVER_*` (локально + VPS).
- Одобрение руководителя **один раз** на MAX сотрудника (`trusted_login_max_user_id`);
  дальше вход только подтверждением в MAX.

## 2026-07-25

- Кабинет: упрощённый вход — один путь MAX (вход=регистрация), без вкладок Вход/Регистрация; SMS по-прежнему не публикуется.
- MAX UX для пожилых: чат без `?startapp`; кнопка/сообщение «Подтвердить вход в веб кабинет»; одноразовая ссылка `/?auth=max&t=`; webhook `message_callback`.
- Вход в кабинет: вкладка **MAX** + кнопка «Получить код в MAX» (`/api/portal/auth/otp/request|verify`); код уходит в бот по `max_user_id`, сессия через Supabase `token_hash`. Выложено на VPS (API + cabinet).
- ЮKassa на VPS: в `/opt/sfrfr/.env` прописаны `YOOKASSA_*` (shop `1417002`, live-ключ), `sfrfr-api` перезапущен, `client_available=True`. Webhook URL по Basic Auth только вручную в ЛК ЮKassa (API webhooks — OAuth).
- Google MVP: Calendar + reCAPTCHA на лидах + GSC CLI; Looker/Search Console ops; Gmail/Vision отложены. SoT = Supabase.
- Google Drive: дерево «SFRFR — Пенсионные дела» (`drive-init-tree`), кейсы `drive-case-mkdir` только по `case_id`; ключ disk SA; сканы — в Supabase Storage.
- Google Drive: модуль `integrations/drive`, CLI `drive-list`, ключ `secrets/sfrfr-sheets-disk-*.json` (`GOOGLE_DRIVE_CREDENTIALS_JSON`).
- DOCX ТЗ-10: strip `**`/` из списков/таблиц/заголовков; `*.docx` в `.gitignore`, файл не коммитить (сборка `scripts/render_landing_tz_docx.py`).
- Реализован ТЗ-09: единый portal для mini-app (MAX auth), link_token, deep-link case, CTA уведомлений.
- Реализован ТЗ-08: feedback→RAG registry, rejected вне поиска, тесты приёмки knowledge.
- Реализован ТЗ-07 MVP: публичный lead API, WP CTA выбора канала, MAX /docs+/draft, оплата с fallback.
- Реализован ТЗ-06: amoCRM API, Sheets без ПДн, ЮKassa pay+webhook, тесты RLS/Storage/Sheets.
- Реализован ТЗ-05: health/ops, безопасные логи, CI gate, ранбук.
- Логотип для светлого фона на витрине (Astra + favicon + hero) и в иконках cabinet/admin.
- Письмо reg.ru: DNS `cabinet`/`admin` добавлены; порты 80/443 открыты. Подняты HTTPS + Next.js кабинеты на VPS (пароль root от них **не нужен** — есть deploy key).
- Накатил миграции Supabase + CLI `staff-grant`/`staff-list` для первого admin.
- Реализован ТЗ-04 кабинет сотрудников с учётом ТЗ-09 (каналы MAX/веб в дашборде и карточке; admin не в mini-app).
- Реализован ТЗ-03 клиентский кабинет: экраны входа/дел/карточки/согласий/оплат/результата + portal API.
- Решение по опыту DeepSeek: **не дообучать** модель на переписках; контур = обезличивание → кейсы → эксперт → RAG.
- В Agent mode реализованы реестр `knowledge/cases`, импорт, статусы качества, фильтр RAG, системный промпт помощника.
- CLI пакетного обезличивания: `sfrfr knowledge-depersonalize-dir inbox/ --out cleaned/`.
- ТЗ-09 этап C: ЮKassa в mini-app/cabinet, результат и сообщения, webhook статусов.
- Для пилота нужны 3–5 обезличенных экспортов диалогов (md/txt/json/html).

## Контекст

- Монетизация сопровождения пенсионного перерасчёта для инвалидов.
- Обращение в ZeroCoder: куратор + стратегия автоматизации.
- Запрос: структура папок, зависимости, окружение, Git, библиотеки.

## Решения

- Стек MVP: FastAPI + Supabase/Postgres + Tesseract OCR + LLM/RAG.
- Модель продукта: диагностика + сопровождение + success fee.
- B2C only: оферта + индивидуальный заказ; amoCRM; чек-листы индивидуально; Sheets без ПДн.
- Success fee: 10% ЕДВ + 50% от суммы прибавок за 3 месяца; постоплата через 2–3 месяца после повышения; 6 месяцев молчания → эскалация/суд (после юриста).
- AI: pipeline-оркестратор + узкие агенты (не swarm); сверка — детерминированный код.
- API/CLI завязаны на `CaseStore` + local upload + OCR при `advance`/`run`.
- Клиентский канал: MAX Bot API; LLM-провайдер: Yandex AI Studio.
- Витрина: WordPress на VPS; API на поддомене; DNS reg.ru.
- Сайт витрины: домен `https://taxi-doroga-dobra.ru/` (reg.ru) — **витрина и посадочная SFRFR**; на VPS в отдельной папке (не в `/opt/sfrfr`). API: `api.taxi-doroga-dobra.ru`.
- Витрина: тема Zakra + блоки; CTA MAX — заглушка `#` / «скоро» до появления deeplink.
- `PUBLIC_BASE_URL` на VPS: `https://api.taxi-doroga-dobra.ru`; `MAX_BOT_TOKEN` пока пуст → webhook не подписан.
- Публичный сайт ТЗ-02 этап 1: лендинг + оферта + ПДн/согласие + кнопка MAX + форма лида (WPForms, без сканов).
- Кабинет v1 мини-приложения: статус дела + загрузка документов; URL `https://taxi-doroga-dobra.ru/app/`; технический username бота `id8905998693_1_bot`.
- Кнопка на лендинге: «Открыть в MAX» → `https://max.ru/id8905998693_1_bot?startapp` (username из `/me`, не StazhIPensiyaBot).

## 2026-07-27 — CTA «Задать вопрос» + FAQ
- CTA mid/end/archive/seed: «Задать вопрос в MAX» + «Оставить заявку» (#zayavka) + «Начать проверку».
- Обновлены FAQ на главной и статья /blog/chastye-voprosy-o-proverke-stazha/.


## 2026-07-27 — правки лендинга (карточки/FAQ/docs)
- Равная высота карточек в ряду; «Что проверяем» в 2 колонки; убраны дубли номеров и бренда в hero.
- Подзаголовок тарифов; reCAPTCHA слева; страница /cookies/ + ссылки в футере и у формы.


## 2026-07-28 — воронка заявки
- amoCRM обязателен для public lead; WP блокирует «успех» при ошибке API; канал в форме; notify MAX менеджерам.

