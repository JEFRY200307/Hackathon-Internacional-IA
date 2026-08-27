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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
