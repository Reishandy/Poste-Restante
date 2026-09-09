import base64
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.blob.router import router as blob_router
from src.config import settings
from src.database import database, get_database
from src.hpke.keys import SUITE, load_or_generate_node_keys
from src.schemas import ErrorResponse, HealthCheckResponse, HealthCheckSuccessResponse, HealthCheckDegradedResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.internal_dispatch_token = secrets.token_hex(32)

    await database.connect()
    await database.create_indexes()

    priv_bytes, pub_bytes = load_or_generate_node_keys()
    app.state.hpke_private_key = SUITE.kem.deserialize_private_key(priv_bytes)
    app.state.hpke_public_key = SUITE.kem.deserialize_public_key(pub_bytes)
    app.state.hpke_public_key_b64 = base64.b64encode(pub_bytes).decode()

    yield
    await database.close()


app = FastAPI(
    title="Poste Restante Storage Service",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal Server Error",
        },
    },
    swagger_ui_parameters={"supportedSubmitMethods": []},
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg: str = str(exc) if settings.DEV_MODE else "Internal server error"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_msg},
    )


@app.get(
    "/",
    tags=[f"App: {settings.APP_NAME}"],
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
async def health_check_endpoint(
        request: Request,
        response: Response,
        db: AsyncIOMotorDatabase = Depends(get_database),
) -> HealthCheckResponse:
    try:
        await db.client.admin.command("ping")
        db_status = "ok"
        server_status = "ok"
    except Exception:
        db_status = "Unreachable"
        server_status = "Degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthCheckResponse(
        detail=server_status,
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
        hpke_public_key=request.app.state.hpke_public_key_b64,
    )


app.include_router(blob_router)
