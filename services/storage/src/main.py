from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.database import database
from src.schemas import ErrorResponse, HealthCheckResponse, HealthCheckSuccessResponse, HealthCheckDegradedResponse
from src.blob.router import router as blob_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    await database.create_indexes()
    yield
    await database.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "internal server error",
        },
    },
)

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

@app.get(
    "/",
    tags=["Root"],
    summary="Health Check",
    description="Endpoint to check the health status of the Server.",
    response_model=HealthCheckResponse,
    responses={
        status.HTTP_200_OK: {
            "model": HealthCheckSuccessResponse,
            "description": "Service is operational",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthCheckDegradedResponse,
            "description": "Database is unreachable",
        },
    },
)
async def health_check_endpoint(response: Response) -> HealthCheckResponse:
    try:
        await database.client.admin.command("ping")
        db_status = "ok"
        server_status = "ok"
    except Exception:
        db_status = "unreachable"
        server_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthCheckResponse(
        detail=server_status,
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
    )

app.include_router(blob_router)