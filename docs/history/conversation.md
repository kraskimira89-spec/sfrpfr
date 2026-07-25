# История беседы (кратко)

## 2026-07-25 (вечер)

- Синхронизация веб-мастера и MAX: шаг «Начать» ↔ кнопка «Начать»; шаг 3 ↔ код + «Подтвердить вход»; без ложных confirm и ручного `/start`.
- Кабинет клиента: интерактивный мастер входа MAX (3 шага); лендинг/miniapp → `?channel=max&from=landing`.

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

## 2026-07-24

- Лендинг: усиленный hero, блок ситуаций (`#situacii`), блок для родственников (`#rodstvenniki`); без обещаний перерасчёта.
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
- Реализован ТЗ-06: Taganay webhook, Sheets без ПДн, ЮKassa pay+webhook, тесты RLS/Storage/Sheets.
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
- B2C only: оферта + индивидуальный заказ; CRM Taganay; чек-листы индивидуально; Sheets без ПДн.
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
