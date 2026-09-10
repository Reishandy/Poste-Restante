from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global configuration for the OHTTP relay server."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = Field(
        "Poste Restante Relay Service",
        description="Name of the server instance",
    )
    APP_VERSION: str = Field("1.0.0", description="Version of the server")
    DEV_MODE: bool = Field(False, description="Development mode flag")

    REQUEST_TIMEOUT_SECONDS: float = Field(
        15.0,
        description="Connection and read timeout when forwarding to storage",
    )

    RATE_LIMIT_REQUESTS: int = Field(
        150,
        description="Maximum requests permitted per IP within the window",
    )
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        60,
        description="Sliding window duration in seconds",
    )


settings = Config()
