from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from src.relay.router import router as relay_router
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.schemas import HealthCheckResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS, connect=5.0)
    ) as client:
        app.state.http_client = client
        yield


tags_metadata = [
    {
        "name": "Service Discovery",
        "description": "Public health check and status discovery.",
    },
    {
        "name": "Relay",
        "description": "Blind OHTTP forwarding endpoint (RFC 9458).",
    },
]

app = FastAPI(
    title="Poste Restante — Relay Service",
    description="Stateless, blind Oblivious HTTP relay node.",
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
        headers=exc.headers,
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
    description="Endpoint to check relay operational status.",
    response_model=HealthCheckResponse,
    responses={
        status.HTTP_200_OK: {
            "model": HealthCheckResponse,
            "description": "Service is operational",
        },
    },
)
async def health_check_endpoint(response: Response) -> HealthCheckResponse:
    return HealthCheckResponse(
        detail="ok",
        app=settings.APP_NAME,
        service="relay",
        version=settings.APP_VERSION,
    )


app.include_router(relay_router)
