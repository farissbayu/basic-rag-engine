from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"
    DATABASE_URL: str = "sqlite:///database.db"
    UPLOAD_DIR: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
