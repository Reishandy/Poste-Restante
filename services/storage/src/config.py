from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global app config, read from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Poste Restante Storage Service"
    APP_VERSION: str = "1.0.0"

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "poste_restante_storage_db"


settings = Config()
