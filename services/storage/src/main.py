from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette import status

from config import settings
from database import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


class HealthCheckResponse(BaseModel):
    service: str = Field(..., description="Service name.", example=settings.APP_NAME)
    version: str = Field(..., description="Service version.", example=settings.APP_VERSION)
    status: str = Field(..., description="Service status.", example="ok")
    database: str = Field(..., description="Database status.", example="ok")


@app.get(
    "/",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Health Check"],
    summary="Health Check",
    description="Endpoint to check the health status of the API.",
    responses={
        status.HTTP_200_OK: {
            "description": "Service is operational.",
            "content": {
                "application/json": {
                    "example": {
                        "service": settings.APP_NAME,
                        "version": settings.APP_VERSION,
                        "status": "ok",
                        "database": "ok"
                    }
                }
            },
        }
        # TODO: Add 500 response example if needed?
    }
)
async def health_check_endpoint():
    """
    Health check endpoint.
    Returns a simple JSON response indicating the service's operational status and database connectivity.
    """
    try:
        await database.client.admin.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok",
        "database": db_status
    }
