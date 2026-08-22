# ТЗ: интеграции и безопасность

## Технологии

| Слой | Решение |
|---|---|
| Публичный сайт | WordPress с лёгкой темой, Elementor или Spectra |
| Кабинеты | React/Next.js или React/Vite |
| API | FastAPI |
| Авторизация и БД | Supabase (MVP: Cloud; целевой: self-hosted в Yandex Cloud, ТЗ-15) |
| Документы | Supabase Storage, private bucket (целевой: Object Storage в РФ, ТЗ-15) |
| CRM | amoCRM (ТЗ-12) |
| Сообщения | MAX Bot API |
| AI | Yandex AI Studio |
| Captcha | MVP: Google reCAPTCHA Enterprise; пилот/целевой: Yandex SmartCaptcha (`CAPTCHA_PROVIDER`, `integrations/smartcaptcha`, ТЗ-15) |
| Аналитика | Google Sheets, обезличенные данные |
| Оплаты | ЮKassa или иной провайдер с чеками |

## Интеграции

### MAX

- Принимать обновления по HTTPS webhook на `api.домен`.
- Клиентский диалог и уведомления идут через бот.
- Кейс и документы остаются источником истины в API/Supabase.

### Yandex AI Studio

- Применять для классификации, извлечения, обоснования findings и черновиков.
- **Модели (по умолчанию):** все роли — `deepseek-v4-flash` в Yandex AI Studio.
  - classify / extract / reason / draft → DeepSeek;
  - YandexGPT не используется (если в `.env` остался `yandexgpt*`, код подменяет на DeepSeek).
- Чатбот MAX (свободный текст) и подсказки ответов сотруднику — тоже DeepSeek (ТЗ-26).
- `analysis_notes` хранится в `case_pipeline_data` и виден **эксперту/админу**; клиенту не отдаём.
- Маскировать ПДн до передачи в модель (`redact_for_llm` / `x-data-logging-enabled: false`).
- Не использовать LLM для детерминированной сверки ИЛС и трудовой.
- Не использовать LLM как основной OCR: сканы — Yandex Vision / Tesseract (см. [13-document-ingest-v2.md](13-document-ingest-v2.md)).
- DeepSeek R1 self-host на GPU — вне MVP; в AI Studio используем managed DeepSeek V4 Flash.

### Яндекс Workspace (ID)

- Почта / Телемост / календарь под `proverkastaza@yandex.ru` через OAuth — [14-yandex-workspace.md](14-yandex-workspace.md).
- Настройка: [../ops/yandex-workspace-setup.md](../ops/yandex-workspace-setup.md).
- Не путать с API-ключом Cloud AI; ПДн-сканы на Яндекс.Диск не выгружать.

### amoCRM

- Сделка + контакт через API v4; custom fields с `code` (`CASE_ID` и др.) — см. [12-amocrm.md](12-amocrm.md).
- Хранить в CRM минимум данных, нужных для работы с клиентом; связь по `case_id` / `crm_external_id`.
- Файлы и чувствительные ПДн в amo не передавать.
- Настройка: [../ops/amocrm-setup.md](../ops/amocrm-setup.md).

### Google Sheets

- Разрешены только обезличенные аналитические поля.
- Запрещены ФИО, телефоны, СНИЛС, номера документов, файлы и тексты OCR.

## Защита ПДн

- Supabase RLS ограничивает строки текущим пользователем и назначенными сотрудниками.
- Документы хранятся в private bucket.
- Для доступа выдаются signed URL с коротким TTL.
- Все скачивания, загрузки, смены прав и акцепты фиксируются в audit log.
- `SUPABASE_SERVICE_ROLE_KEY` используется только серверной частью FastAPI.
- Локализация баз в РФ и отказ от иностранного Cloud после MVP — [15-data-localization-ru.md](15-data-localization-ru.md).

## Критерии приёмки

- Проверки RLS покрыты интеграционными тестами.
- Открытая ссылка на Storage не даёт доступ к файлу.
- В Google Sheets отсутствуют ПДн.
