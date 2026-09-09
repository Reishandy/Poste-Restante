from typing import Literal

from pydantic import BaseModel, Field

from src.config import settings


class Response(BaseModel):
    """Base response model for consistency"""
    detail: str = Field(
        ...,
        description="The response detail",
        examples=["ok"]
    )


class ErrorResponse(Response):
    detail: str = Field(
        default="Internal server error",
        description="The error detail",
        examples=["Internal server error"],
    )


class HealthCheckResponse(Response):
    service: str = Field(
        default=settings.APP_NAME,
        description="Service name",
        examples=[settings.APP_NAME],
    )
    version: str = Field(
        default=settings.APP_VERSION,
        description="Service version",
        examples=[settings.APP_VERSION],
    )
    database: str = Field(..., description="Database status", examples=["ok"])
    hpke_public_key: str = Field(
        ...,
        description="Base64-encoded HPKE public key for this service)",
        examples=["3z5V9k2t1Q...base64..."],
    )


class HealthCheckSuccessResponse(HealthCheckResponse):
    detail: Literal["ok"] = Field(
        default="ok",
        description="The response detail",
        examples=["ok"],
    )
    database: Literal["ok"] = Field(
        default="ok",
        description="Database status",
        examples=["ok"],
    )


class HealthCheckDegradedResponse(HealthCheckResponse):
    detail: Literal["degraded"] = Field(
        default="degraded",
        description="The response detail",
        examples=["degraded"],
    )
    database: Literal["unreachable"] = Field(
        default="unreachable",
        description="Database status",
        examples=["unreachable"],
    )
