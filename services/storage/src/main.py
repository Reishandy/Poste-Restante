from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


# Custom exception handler to change {detail} to {message} for more unified response
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg: str = str(exc) if settings.DEV_MODE else "Internal server error"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": error_msg},
    )


class HealthCheckResponse(BaseModel):
    service: str = Field(..., description="Service name.", examples=[settings.APP_NAME])
    version: str = Field(..., description="Service version.", examples=[settings.APP_VERSION])
    status: str = Field(..., description="Service status.", examples=["ok"])
    database: str = Field(..., description="Database status.", examples=["ok"])


@app.get(
    "/",
    tags=["Root"],
    summary="Health Check",
    description="Endpoint to check the health status of the Server.",
    response_model=HealthCheckResponse,
    responses={
        status.HTTP_200_OK: {
            "model": HealthCheckResponse,
            "description": "Service is operational",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthCheckResponse,
            "description": "Database is unreachable",
        },
    },
)
async def health_check_endpoint(response: Response):
    """
    Health check endpoint.
    Returns 200 when all systems are operational, or 503 if the database is down.
    """
    try:
        await database.client.admin.command("ping")
        db_status = "ok"
        server_status = "ok"
    except Exception:
        db_status = "unreachable"
        server_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthCheckResponse(
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        status=server_status,
        database=db_status,
    )
