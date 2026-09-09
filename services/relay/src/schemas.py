from pydantic import BaseModel, Field

from src.config import settings


class Response(BaseModel):
    """Base response schema."""

    detail: str = Field(
        ..., description="The response detail", examples=["ok"]
    )


class ErrorResponse(Response):
    detail: str = Field(
        default="Internal server error",
        description="The error detail",
        examples=["Internal Server Error"],
    )


class HealthCheckResponse(Response):
    app: str = Field(
        default=settings.APP_NAME,
        description="Application name",
        examples=["Poste Restante Relay Service"],
    )
    service: str = Field(
        default="relay",
        description="Service identifier",
        examples=["relay"],
    )
    version: str = Field(
        default=settings.APP_VERSION,
        description="Service version",
        examples=[settings.APP_VERSION],
    )
