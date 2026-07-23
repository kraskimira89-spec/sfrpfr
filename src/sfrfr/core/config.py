from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_debug: bool = True
    app_secret_key: str = "change-me"
    app_name: str = "SFRFR"
    public_base_url: str = "https://api.taxi-doroga-dobra.ru"
    cors_allowed_origins: str = (
        "https://taxi-doroga-dobra.ru,"
        "https://www.taxi-doroga-dobra.ru,"
        "https://cabinet.taxi-doroga-dobra.ru,"
        "https://admin.taxi-doroga-dobra.ru"
    )

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
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
    yandex_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    embedding_model: str = "text-embedding-3-small"

    max_bot_token: str = ""
    max_api_base: str = "https://platform-api2.max.ru"
    max_webhook_secret: str = ""

    pii_encryption_key: str = ""
    data_retention_days: int = 90
    require_consent: bool = True

    default_diagnostic_price_rub: int = 3000
    success_fee_percent: int = 10
    taganay_case_url_template: str = "https://taganay.clientbase.ru/"
    cabinet_public_url: str = "https://cabinet.taxi-doroga-dobra.ru"
    max_public_bot_url: str = "https://max.ru/id8905998693_1_bot?startapp"
    max_miniapp_url: str = "https://taxi-doroga-dobra.ru/app/"

    # Эксплуатация / мониторинг (ТЗ-05)
    ops_monitor_token: str = ""
    ops_failed_alert_threshold: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
