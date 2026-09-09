import base64
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.database import database, get_database
from src.mailbox.router import router as mailbox_router
from src.ohttp.keys import SUITE, load_or_generate_node_keys
from src.ohttp.router import router as ohttp_router
from src.schemas import HealthCheckResponse, HealthCheckSuccessResponse, HealthCheckDegradedResponse


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


tags_metadata = [
    {
        "name": "Service Discovery",
        "description": "Public health status and cryptographic identity discovery.",
    },
    {
        "name": "OHTTP Gateway",
        "description": (
            "RFC 9458 encapsulated gateway. All mailbox operations (read/write/delete) "
            "must pass through `/ohttp` sealed against the node's HPKE public key."
        ),
    },
    {
        "name": "Mailbox Storage (Encapsulated)",
        "description": (
            "Inner endpoints executed via ASGI loopback. Direct external HTTP access "
            "returns `403 Forbidden` these endpoints only process requests arriving "
            "inside a decapsulated Binary HTTP (RFC 9292) envelope."
        ),
    },
]

app = FastAPI(
    title="Poste Restante — Storage Service",
    description="A stateless, blind key-value store holding encrypted mailbox payloads.",
    version=settings.APP_VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
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
    tags=["Service Discovery"],
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
        app=settings.APP_NAME,
        service="storage",
        version=settings.APP_VERSION,
        database=db_status,
        hpke_public_key=request.app.state.hpke_public_key_b64,
    )


app.include_router(mailbox_router)
app.include_router(ohttp_router)
