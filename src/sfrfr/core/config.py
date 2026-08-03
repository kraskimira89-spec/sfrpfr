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
    yandex_model: str = "yandexgpt/latest"
    # Dual-model: classify (дёшево) / analyze (DeepSeek via YC) / draft (YandexGPT Pro)
    yandex_model_classify: str = "yandexgpt-lite/latest"
    yandex_model_analyze: str = "deepseek-v4-flash"
    yandex_model_draft: str = "yandexgpt/latest"
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
    cabinet_public_url: str = "https://cabinet.proverkastaza.ru"
    admin_public_url: str = "https://admin.proverkastaza.ru"
    # MAX user_id руководителей (через запятую) — подтверждение входа сотрудников
    staff_login_approver_max_user_ids: str = ""
    # chat_id диалогов руководителей (через запятую, тот же порядок что user_id)
    staff_login_approver_max_chat_ids: str = ""
    # Диалог с ботом (вход / «написать боту») — без ?startapp
    max_chat_url: str = "https://max.ru/id8905998693_1_bot"
    # Deep-link на mini-app (?startapp) — лендинг, открытие приложения
    max_public_bot_url: str = "https://max.ru/id8905998693_1_bot?startapp"
    max_miniapp_url: str = "https://proverkastaza.ru/app/"

    # Эксплуатация / мониторинг (ТЗ-05)
    ops_monitor_token: str = ""
    ops_failed_alert_threshold: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
