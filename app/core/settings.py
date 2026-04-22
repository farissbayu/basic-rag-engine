from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str = "https://api.minimax.io/v1"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
