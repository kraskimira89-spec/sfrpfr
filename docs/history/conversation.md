# История бесед

## 2026-08-13 — форма заявки в две карточки

- Имя и контакты рядом; согласие и «Обязательное заполнение» на всю ширину под ними.

## 2026-08-13 — кнопка MAX в фирменных цветах

- Плавающая «Чат MAX»: градиент брендбука (#00BFFF → #471AFF → #9500FF) и иконка облачка.

## 2026-08-13 — заявка как главное действие на главной

- Зелёные CTA: «Оставить заявку» (#zayavka); MAX — плавающая кнопка справа, как BVI.
- На телефоне sticky тоже на форму; боковой MAX скрыт, чтобы не дублировать.

## 2026-08-13 — форма заявки без кнопки MAX

- Заголовок блока `#zayavka`: «Оставить заявку»; кнопка MAX над формой убрана.

## 2026-08-12 — бейдж рейтинга + печатные материалы Sprav

- Скопированы `docs/brand/card.pdf` / `booklet.pdf` в promo; QR взят из рабочей картинки визитки (чёрный экспорт отброшен).
- Виджет рейтинга `82469923047` на `/kontakty/` и в футере сайта.

## 2026-08-12 — канон Яндекс Бизнеса `82469923047`

- Владелец: дубликат `234170727274` удалён, осталась `82469923047`.
- Обновлены форма отзывов, QR, kontakty, config, уведомления, шаблоны, тесты, ops.

## 2026-08-12 — две карточки Яндекс Бизнеса

- Публично: `82469923047` (полный прайс 4 поз.) и дубликат `234170727274` (3 поз., старые ссылки на отзывы).
- У обеих в Картах отзывов нет. YML/сайт/фид совпадают с каноном.
- Ссылки на отзывы не трогали; чеклист слияния в ops + `docs/history/2026-08-12-yandex-business-dual-cards.md`.

## 2026-08-12 — локальный Manrope без Google Fonts

- Пользователь: скачать шрифты, без онлайн Google Fonts.
- Сделано: woff2 в `scripts/assets/fonts/manrope/`, CSS `@font-face`, копирование в WP uploads при apply/seed.

## 2026-08-12 — лиды в канал команды + чеклист VPS

- Wiring: `MAX_SPECIALISTS_CHANNEL_*` в config; новый лид → пост в канал через ops-бот.
- Чеклист команд VPS в `docs/ops/max-ops-bot-setup.md`.

## 2026-08-11 — Ops-бот MAX (ТЗ-25)

- Пользователь: отдельный чат для админа/специалистов, не смешивать с клиентским ботом.
- Согласовано: второй бот (Ops), клиентский UX без изменений; специалист по-прежнему может войти в клиентский диалог.
- В коде: webhook `/ops`, notify лидов/approve через ops, docs + CLI. Нужен токен второго бота на VPS.

## 2026-08-09 — wipe тестовых данных + старт QA

- ВМ YC была STOPPED → start; очищены clients/cases/auth (кроме staff admin).
- Следующий тест: `+79091950408`.

## 2026-08-05 — позицию «готовим / подаёте сами» использовать везде

- Пользователь: после дисклеймера в блоге — ту же формулировку на всех поверхностях.
- Сделано: эталон + код `core/copy.py`, сайт, футер, бот MAX, API, оферта, черновики канала.

## 2026-08-03 — промо QR + мягкие просьбы об отзыве

- Форма: https://yandex.ru/sprav/234170727274/reviews/add/
- Исправлен битый `assets/qr.png`; промо в `scripts/assets/yandex-business/promo/`.
- Шаблоны MAX короче и без навязчивости; QR на `/kontakty/`.

## 2026-08-03 — ТЗ-19 сбор отзывов

- По статье Яндекса о мотивации отзывов: ТЗ + ops + шаблоны MAX/ответов без накруток и бонусов.
- Ручной шаг: скопировать URL формы из Sprav `234170727274` в `secrets/yandex-business-review.env`.

## 2026-08-03 — ТЗ-18 недели 2–3 доверие/коммерция

- Страницы `/proverka-stazha/`, `/tarify/`, `/kak-rabotaem/`, `/kontakty/`, `/expert/lopakova-nataliya/`.
- Byline автора/проверяющего; единые реквизиты; `tariff_view` на `/tarify/`.

## 2026-08-03 — документы и production-контур РФ

- Проверен production: Supabase/API/dbt → Yandex Cloud, captcha → SmartCaptcha.
- По просьбе пользователя на всех юридических страницах добавлен спойлер с историей редакций.
- После итоговой сверки синхронизирован пункт 7.3 правил браузера и удалена загрузка Google Fonts из MAX.
- Выявленные хвосты Google Sheets отключены в API, CLI и адаптере production.
- Иностранные LLM запрещены в production; Yandex AI Studio остаётся основным контуром.
- Подготовлены и опубликованы новые редакции Политики, Согласия и Правил файлов браузера.

## 2026-08-03 — DeepSeek platform fallback

- Проверен API-ключ (`200`, `deepseek-chat`).
- Сохранён в `secrets/deepseek.env` + локальный `.env`; в коде — запасной `LLMClient`.

## 2026-08-03 — dbt/DATABASE_URL → YC + drain checklist

- SG: `allowed_postgres_cidrs` (VPS + admin) на 5432/5433.
- Прямой PG `:5433` (`docker-compose.sfrfr-direct-pg.yml`); Supavisor остаётся на `:5432`.
- VPS `DATABASE_URL`/`DBT_*` → `51.250.13.240:5433`; `dbt debug` OK.
- Чеклист drain Cloud: `docs/ops/supabase-cloud-drain-checklist.md` (без удаления проекта).

## 2026-08-03 — cutover Supabase Cloud → YC

- Импорт данных в self-host (11 clients / 9 cases / 10 users; 0 SYNTH).
- VPS `.env` + cabinet/admin пересобраны на `https://supabase.proverkastaza.ru`.
- API health 200; service_role видит данные. Cloud пока не drain.
- GoTrue `ADDITIONAL_REDIRECT_URLS` → cabinet/** + recover + admin/** (`yc_set_auth_redirects.sh`).
- Пароли Auth пустые после импорта — вход через magic link / OTP.
- Хвост: `DATABASE_URL`/`DBT_HOST` на VPS ещё Cloud (приложение ходит через Supabase HTTP; dbt — отдельно).

## 2026-08-03 — DNS supabase + HTTPS staging

- В reg.ru A `supabase` → `51.250.13.240`; DNS резолвится.
- Caddy перезапущен; Let's Encrypt выдан; `https://supabase.proverkastaza.ru` отвечает.

## 2026-08-02 — проверка/хвосты ТЗ-16

- `tofu plan`: No changes (drift нет).
- Lockbox + миграции + seed уже были ✅.
- DNS NXDOMAIN: скрипты `regru_add_supabase_a.py`, `wait_supabase_dns_and_tls.ps1`; тикет/доки обновлены.
- Блокер HTTPS: A `supabase` → `51.250.13.240` в reg.ru (нужны API-креды или ручной клик).

## 2026-08-02 — ТЗ-15 рекомендации фазы 1

Реализованы скрипты/код: Caddy, миграции+seed, backup/restore-drill, SmartCaptcha модуль.
Ручной хвост пользователя: DNS A `supabase` в reg.ru; ключи SmartCaptcha в YC.

## 2026-08-02 — Lockbox supabase-config (не создавать)

Пользователь/консольный AI: создать `supabase-config` с placeholder JWT.
Ответ: **не создавать**; дубль удалён. SoT — Terraform Lockbox + `secrets/supabase-staging.env`.
Compose на staging ВМ поднят (healthy); публично 8000 закрыт SG.

## 2026-08-02 — рекомендации Terraform plan

Пользователь: реализовать рекомендации (yc + plan, не apply).
Сделано: YC CLI 1.22.0, скрипты auth/plan, ops-док. Plan заблокирован — нужен Cloud OAuth (`cloud:auth`); Workspace/API key отклонены.ы (кратко)

## 2026-08-02 (YC staging apply)

- SA terraform + admin; tofu apply OK; IP 51.250.13.240; next Lockbox/Supabase.

## 2026-08-02 (сохранение analysis_notes)

- Реализована рекомендация: notes в БД + кабинет эксперта; клиенту не показываем.

## 2026-08-02 (шаг 4: связка DeepSeek + YandexGPT)

- В AI Studio managed: DeepSeek V4 Flash (не self-host R1).
- Связка в коде: анализ/извлечение → DeepSeek; черновик → YandexGPT Pro; сверка — код.
- ПДн: redact + anti-logging header.

## 2026-08-02 (пошаговая настройка AI Studio)

- Разблокировка/активация cloud `sfrfr-ai`, trial 500 ₽.
- SA + API-ключ (тип: API-ключ, не static/authorized).
- UI тест «работает» → запись в secrets/.env → smoke LLMClient OK.

## 2026-07-29 (запрет автопересида ситуаций)

- Исправлен truncate seo_title в генераторе; generate/seed situations запрещены по умолчанию.
- Политика: статьи только вручную; ИИ — рекомендации.

## 2026-07-29 (SEO-рекомендации аудита статей)

- Реализована карта URL + hub-статьи своим ИИ (не YandexGPT).
- noindex ситуаций, repair meta description, 301 glavnaya, убран дубль CTA в сидере.
- Деплой одним заходом в конце после повторного аудита.

## 2026-07-29 (противоречие Метрики и согласия)

- Реализована схема: внутренняя агрегация для всех + Метрика только после Allow.
- Обновлены cookies/контракт; Playwright на Allow и Deny.

## 2026-07-29 (проход TOC Метрика/Вебмастер)

- По разделам P0/P1: дозакрыты recrawl, smoke Reports, Clean-param, sample-page.
- Самотест API + Playwright; деплой одним заходом в конце.

## 2026-07-29 (чеклист Метрики P0/P1)

- Согласие до загрузки счётчика; P1-цели; фильтры роботов/IP/URL-params.
- Playwright: deny блокирует, allow грузит tag.js, reachGoal всех кодов в сети.
- IP запуска в exclude — тестовые хиты в отчётах могут не отображаться.

## 2026-07-29 (рекомендации Вебмастера)

- Sitemap добавлен через API; ensure-скрипт умеет повторять.
- Главное зеркало: Apache 301 www/http → https apex (через API задать нельзя).

## 2026-07-29 (токен Вебмастера → API)

- Пользователь вставил OAuth `y0_…` в `secrets/yandex-webmaster.env`.
- Добавлены/подтверждены зеркала https и www; все VERIFIED.
- Гайд: `docs/ops/yandex-webmaster-setup.md`.

## 2026-07-29 (разбор ответа ассистента консоли + Terraform в git)

- Ассистент YC выдал полный черновик TF; в репо файлов не было.
- Исправления: SA на VM, validation SSH, virtio device_name, folder IAM storage.uploader.
- Код в `infra/yandex-cloud/`; apply не выполнялся.

## 2026-07-29 (промпт ассистента консоли YC)

- `docs/specs/ии яндекс клоуд ВМ` переписан под AI-ассистента консоли (не Cursor): SFRFR folder/cloud, staging VM, без git.

## 2026-07-29 (утверждён DataLens вместо Sheets)

- Полная замена Google Таблиц: dbt marts → DataLens; SheetsExporter только после сверки KPI.
- Альтернативы: admin резерв, amoCRM sales, Яндекс Таблицы — временный tabular.

## 2026-07-29 (ТЗ замены аналитического плагина)

- Подготовлено ТЗ-17: DataLens / amoCRM / admin как параллельные POC.
- dbt Core оставлен baseline; отдельно предусмотрен пилот замены на SQL views.
- Уточнено: заменяется Google Sheets/Looker; Метрика покрывает только веб-воронку.

## 2026-07-29 (задание AI-ассистенту Yandex Cloud)

- Подготовлены ТЗ-16 и paste-ready задача на Terraform staging под текущий folder.
- Зафиксировано: код/plan без apply, prod/DNS не трогать, Managed PG/K8s — позже.

## 2026-07-28 (webhook ЮKassa URL)

- В ЛК был URL без /webhook (404); добавлен алиас POST .../yookassa.

## 2026-07-28 (ОФД / Evotor)

- Канон: ЮKassa → Evotor → Платформа ОФД; CLI yookassa-status; без двойной фискализации.

## 2026-07-28 (оплата: MAX + amoCRM)

- Уже в коде: notify после succeeded → MAX/чат дела + заметка amo; чек только ЮKassa.
- Лог ошибки notify в webhook без падения 200.

## 2026-07-28 (оплата: MAX + amo)

- После payment.succeeded: MAX/чат дела + заметка amo; чек только ЮKassa.

## 2026-07-28 (ЮKassa / ЮMoney)

- Магазин live nabled; в methods есть yoo_money.
- Создание платежа падало: фискализация вкл., SEND_RECEIPT=false → Receipt is missing.
- Вкл. чеки + return_url на cabinet.proverkastaza.ru; pay требует email при чеке.

## 2026-08-02 (Google → Yandex SmartCaptcha)

- Витрина: виджет SmartCaptcha при `SMARTCAPTCHA_CLIENT_KEY=ysc1_…`.
- API: `CAPTCHA_PROVIDER=yandex` + `SMARTCAPTCHA_SERVER_KEY`.
- Без ключей Yandex — fallback на Google Enterprise (legacy).
- Прод: ключи капчи `proverkastaza` (хосты proverkastaza.ru / www) записаны в `/opt/sfrfr/.env`, виджет + validate включены.

## 2026-08-03 (форма заявки «ничего не происходит»)

- Баг: кнопка disabled → `requestSubmit(disabled)` → InvalidStateError, отправка молчала.
- Фикс JS + явный `smartCaptcha.render` для динамического виджета.

## 2026-08-03 (регистрация без дубля полей заявки)

- Success WPForms: ссылка с `email/phone/name/from_lead` из ответа API.
- Кабинет: при prefill — сводка контактов + СОПД + «Получить код», без повторного ввода.

## 2026-08-03 (письма Auth по-русски)

- Шаблоны confirmation/magic_link/recovery: бренд «Проверка стажа», имя, код `{{ .Token }}`.
- Применение: `scripts/supabase_patch_auth_emails.py` + PAT в `secrets/supabase-access.env`.

## 2026-08-05 (публичная почта info@proverkastaza.ru)

- Заменён `prismotr89@yandex.ru` → `info@proverkastaza.ru` (футер, контакты, legal, schema).
- WP `admin_email` + WPForms notifications; API `OPS_NOTIFY_EMAIL` на новые лиды.

## 2026-08-03 (единый favicon на кабинете/admin/MAX)

- Было: дефолтный Next/Vercel `favicon.ico` (чёрный квадрат) на cabinet/admin.
- Заменён на логотип «Проверка стажа» (как на WP); в miniapp добавлены icon-ссылки.

## 2026-08-03 (каталожный номер дела вместо UUID в MAX)

- Формат: `ПС-{YY}-{ИИ}-{NNNNNN}` (пример: `ПС-26-НА-730545`).
- В уведомлении менеджеру: `Дело: ПС-…` вместо сырого UUID.
- UUID остаётся PK в БД; короткий NNNNNN = как прежний «Дело №» из UUID.

## 2026-08-03 (Auth From: Яндекс РФ, не supabase.io)

- Проблема: OTP с `noreply@mail.app.supabase.io` / GoTrue.
- Решение: Auth Send Email Hook → `/api/integrations/supabase/auth-send-email` → SMTP Яндекс.
- From: «Проверка стажа. Личный кабинет» `<proverkastaza@yandex.ru>`.
- Скрипт: `scripts/supabase_enable_auth_send_email_hook.py`; секрет `SUPABASE_SEND_EMAIL_HOOK_SECRET`.


## 2026-08-03 (список документов + краткое содержание)

- После upload: `documents.content_preview` (лёгкий extract), UI список с именем/типом/датой/превью.

## 2026-07-29 (MAX: кнопки навигации)

- Нижняя панель: Обзор / Документы / Сообщения / Мои дела.
- В шапке: «←» назад к делам и кнопка «Дела».
- Горизонтальные вкладки разделов внутри дела.

## 2026-07-29 (номера дел: «Дело №»)

- В MAX miniapp и кабинете дела показываются как «Дело № 12345» + статус по-русски.

## 2026-07-29 (MAX miniapp: Failed to fetch)

- Живой `/app/config.js` указывал на `api.taxi-doroga-dobra.ru` → «Failed to fetch».
- Выложен актуальный miniapp; `vps_deploy.sh` теперь всегда обновляет `/app/`.

## 2026-07-29 (безопасность: фиксированные тарифы)

- На лендинге обновлён блок `#tarify`: опубликованы фиксированные суммы 3 000 / 10 000 / 25 000 ₽.
- Убрана переменная формулировка «от ...» и процентная модель из публичного тарифа.

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

## 2026-07-29 (Метрика live)

- Счётчик API: `111134477`; цели `lead_ok`, `max_click`.
- MU на WP + `YANDEX_METRIKA_COUNTER_ID` на VPS; вебвизор выкл.

## 2026-07-29 (Метрика вариант B: API + WP)

- Гайд `docs/ops/yandex-metrika-setup.md`; скрипт `yandex_metrika_ensure_counter.py`; MU `sfrfr-yandex-metrika.php` + `wp_deploy_metrika.sh`.
- Ждём OAuth ClientID + token (`metrika:read/write`) → ensure + деплой на VPS.

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

## 2026-07-29 — стратегия SEO-продвижения

- По запросу пользователя разработаны стратегия и техническое задание SEO-продвижения `proverkastaza.ru`.
- Проверены production, sitemap, редиректы, метаданные и текущий статус Яндекс Вебмастера.
- Приоритет стратегии: исправление технического P0, консолидация 46 тонких публикаций в сильные кластеры, подтверждаемая экспертность и измерение квалифицированных органических лидов.
- После завершения аудитов начато внедрение P0: SEO MU-plugin, один H1 на запись и запрет индексации `/app/`.
- Структура P0 подтверждена полным production-crawl; добавлен еженедельный автоматический SEO-аудит, который дополнительно проверяет непустое содержимое тегов, и переобход ключевых URL в Яндекс Вебмастере.

