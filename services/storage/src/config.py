from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global app config, read from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = Field("Poste Restante Storage Service", description="Name of the server instance")
    APP_VERSION: str = Field("1.0.0", description="Version of the server")

    MONGO_URI: str = Field("mongodb://localhost:27017", description="MongoDB URI")
    MONGO_DB_NAME: str = Field("poste_restante_storage_db", description="Database name")

    DEV_MODE: bool = Field(False, description="Development mode flag")
    BLOB_EXPIRY_SECONDS: int = Field(7_776_000, description="Expiry in seconds for blob storage")  # Defaults to 90 Days

    HPKE_KEY_DIR: str = Field("./data/keys", description="Directory holding this node's HPKE keypair.")


settings = Config()
