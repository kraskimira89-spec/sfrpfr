from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_debug: bool = True
    app_secret_key: str = "change-me"
    app_name: str = "SFRFR"
    public_base_url: str = "https://api.proverkastaza.ru"
    cors_allowed_origins: str = (
        "https://proverkastaza.ru,"
        "https://www.proverkastaza.ru,"
        "https://cabinet.proverkastaza.ru,"
        "https://admin.proverkastaza.ru"
    )

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # Auth Send Email Hook (Standard Webhooks): v1,whsec_...
    supabase_send_email_hook_secret: str = ""
    database_url: str = "postgresql+psycopg://sfrfr:sfrfr@localhost:5432/sfrfr"

    storage_backend: str = "local"
    storage_local_path: str = "./storage/uploads"
    supabase_storage_bucket: str = "pension-docs"

    ocr_engine: str = "tesseract"
    tesseract_lang: str = "rus+eng"

    ai_provider: str = "yandex"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model: str = "deepseek-v4-flash"
    # Роли LLM в Yandex AI Studio: канон — DeepSeek (не YandexGPT)
    yandex_model_classify: str = "deepseek-v4-flash"
    yandex_model_analyze: str = "deepseek-v4-flash"
    yandex_model_draft: str = "deepseek-v4-flash"
    yandex_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    # DeepSeek platform API — только для локальных экспериментов, не для production-ПДн
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_fallback_enabled: bool = False
    # Яндекс Workspace OAuth (ТЗ-14) — отдельно от Cloud AI
    yandex_oauth_client_id: str = ""
    yandex_oauth_client_secret: str = ""
    yandex_oauth_access_token: str = ""
    yandex_oauth_refresh_token: str = ""
    yandex_workspace_email: str = "proverkastaza@yandex.ru"
    # Отдельное OAuth-приложение только для Телемост (часто нужно 360)
    yandex_telemost_oauth_client_id: str = ""
    yandex_telemost_oauth_client_secret: str = ""
    yandex_telemost_oauth_access_token: str = ""
    yandex_telemost_enabled: bool = True
    yandex_mail_enabled: bool = True
    yandex_mail_imap_enabled: bool = False
    # ТЗ-31: Postmark webhooks (Basic Auth). Отправка пока может идти через Yandex SMTP.
    postmark_webhook_user: str = ""
    postmark_webhook_password: str = ""
    postmark_server_token: str = ""  # опционально, для будущей отправки через Postmark
    email_delivery_hash_salt: str = ""  # пусто = app_secret_key
    yandex_calendar_enabled: bool = True
    yandex_disk_enabled: bool = False
    # Алиасы из раздела «Аналитика» / docs (часто заполнены вместо YANDEX_*)
    llm_api_key: str = ""
    llm_folder_id: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"

    max_bot_token: str = ""
    max_api_base: str = "https://platform-api2.max.ru"
    max_webhook_secret: str = ""
    # ТЗ-25: служебный бот (лиды, approve staff); пусто = fallback на MAX_BOT_TOKEN
    max_ops_bot_token: str = ""
    max_ops_webhook_secret: str = ""
    max_ops_chat_url: str = ""
    # Веб-кабинет MAX Business → диалоги бота (ручной поиск по user_id)
    max_business_dialogs_url: str = "https://business.max.ru/self"
    # ТЗ-27: AI-ответы специалистам в ops / канале команды
    max_ops_llm_enabled: bool = True
    max_ops_llm_max_chars: int = 3500
    # Модель в Yandex AI Studio (канон: DeepSeek V4 Flash), не platform.deepseek.com
    max_ops_llm_model: str = "deepseek-v4-flash"
    # ТЗ-26: LLM-ответ на свободный текст в MAX (DeepSeek via YC)
    max_llm_chat_enabled: bool = True
    max_llm_chat_max_turns: int = 5
    # Внутренний канал команды («Проверка стажа — команда»); не на сайт
    max_specialists_channel_url: str = "https://max.ru/id8905998693_biz"
    max_specialists_channel_chat_id: str = ""

    pii_encryption_key: str = ""
    data_retention_days: int = 90
    require_consent: bool = True

    default_diagnostic_price_rub: int = 3000
    success_fee_percent: int = 10
    # amoCRM API v4 (ТЗ-12)
    amo_subdomain: str = ""
    amo_access_token: str = ""
    amo_pipeline_id: str = ""
    amo_status_id: str = ""
    amo_case_url_template: str = "https://{subdomain}.amocrm.ru/leads/detail/{id}"
    # Google Sheets: API (service account) предпочтительно; webhook — fallback
    google_sheets_spreadsheet_id: str = ""
    google_sheets_worksheet: str = "Analytics"
    # Путь к JSON ключу SA или сам JSON одной строкой
    google_sheets_credentials_json: str = ""
    google_sheets_webhook_url: str = ""
    # Google Drive (отдельный SA JSON; папки шарить на client_email)
    google_drive_credentials_json: str = ""
    google_drive_folder_id: str = ""
    # Google Calendar (SA; календарь расшарить на client_email, события только case_id)
    google_calendar_credentials_json: str = ""
    google_calendar_id: str = ""
    # reCAPTCHA Enterprise (защита публичных лидов; MVP)
    recaptcha_credentials_json: str = ""
    recaptcha_project_id: str = ""
    recaptcha_site_key: str = ""
    recaptcha_min_score: float = 0.5
    # Yandex SmartCaptcha (ТЗ-15; пилот staging / целевой prod)
    # captcha_provider: auto | google | yandex
    captcha_provider: str = "auto"
    smartcaptcha_server_key: str = ""
    smartcaptcha_client_key: str = ""
    # Search Console (ops / SEO)
    google_search_console_credentials_json: str = ""
    # ЮKassa
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_api_base: str = "https://api.yookassa.ru/v3"
    yookassa_return_url: str = ""
    yookassa_send_receipt: bool = False
    public_lead_token: str = ""
    # Куда слать уведомления о новых заявках (email)
    ops_notify_email: str = "info@proverkastaza.ru"
    cabinet_public_url: str = "https://cabinet.proverkastaza.ru"
    admin_public_url: str = "https://admin.proverkastaza.ru"
    # MAX user_id руководителей (через запятую) — подтверждение входа сотрудников
    staff_login_approver_max_user_ids: str = ""
    # chat_id диалогов руководителей (через запятую, тот же порядок что user_id)
    staff_login_approver_max_chat_ids: str = ""
    # Диалог с ботом (вход / «написать боту») — без ?startapp
    max_chat_url: str = "https://max.ru/id8905998693_1_bot"
    # Deep-link на mini-app (?startapp) — открытие из бота после диагностики
    max_public_bot_url: str = "https://max.ru/id8905998693_1_bot?startapp"
    max_miniapp_url: str = "https://proverkastaza.ru/app/"
    # Канал MAX (информирование) — не первичный CTA сайта
    max_channel_url: str = "https://max.ru/channel_proverkastaza"
    # chat_id канала для POST /messages (не публиковать на сайте)
    # channel_proverkastaza; переопределяется .env / VPS
    max_channel_chat_id: str = "-77580376877720"
    # Форма отзыва Яндекс Бизнес (ТЗ-19): ведущая короткая ссылка → Sprav
    yandex_business_review_url: str = "https://proverkastaza.ru/otzyv/"

    # Эксплуатация / мониторинг (ТЗ-05)
    ops_monitor_token: str = ""
    ops_failed_alert_threshold: int = 1

    # Яндекс Трекер — внутренние задачи качества (очередь STAZH)
    tracker_enabled: bool = True
    tracker_token: str = ""  # TRACKER_TOKEN
    tracker_oauth_token: str = ""  # YANDEX_TRACKER_OAUTH_TOKEN (alias)
    tracker_org_id: str = ""  # TRACKER_ORG_ID / YANDEX_TRACKER_ORG_ID
    tracker_cloud_org_id: str = ""
    tracker_queue: str = "STAZH"
    tracker_case_ref_secret: str = ""  # TRACKER_CASE_REF_SECRET


@lru_cache
def get_settings() -> Settings:
    return Settings()
