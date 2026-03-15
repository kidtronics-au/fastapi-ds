from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra='allow')
    openai_api_key: str
    openai_api_base: str
    chat_model: str
    database_url: PostgresDsn
    log_level: str = "INFO"
    embedding_model: str = "nomic-embed-text"


settings = Settings()
