from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV), extra="ignore")

    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_fallback_model: str = "gpt-4o-mini"
    pretrained_model_url: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    whatsapp_enabled: bool = False
    whatsapp_dry_run: bool = True
    whatsapp_app_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_config_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_waba_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_graph_version: str = "v25.0"
    whatsapp_template_name: str = "risa_alert_update"
    whatsapp_template_language: str = "es"
    whatsapp_db_path: str = ".runtime/whatsapp.sqlite3"
    whatsapp_scan_seconds: int = 300
    whatsapp_cooldown_hours: int = 12
    whatsapp_max_notifications_day: int = 2
    whatsapp_quiet_start_hour: int = 21
    whatsapp_quiet_end_hour: int = 8
    whatsapp_medium_risk_threshold: float = 0.7
    whatsapp_admin_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def whatsapp_live_ready(self) -> bool:
        return bool(
            self.whatsapp_access_token
            and self.whatsapp_phone_number_id
            and self.whatsapp_waba_id
            and self.whatsapp_verify_token
            and self.whatsapp_app_secret
        )


settings = Settings()
