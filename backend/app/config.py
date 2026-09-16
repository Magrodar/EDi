from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://edi:change_me@localhost:5432/edi"

    edi_user_email: str = "mahmoud.10987@gmail.com"
    edi_api_key: str = "change_me_to_a_long_random_string"

    edi_llm_provider: str = "stub"          # "stub" | "openai"
    edi_llm_model: str = "gpt-5.6-terra"
    openai_api_key: str | None = None

    edi_embeddings_provider: str = "stub"   # "stub" | "openai"

    edi_alert_cooldown_minutes: int = 180


settings = Settings()
