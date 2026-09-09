import httpx
from fastapi import HTTPException
from starlette import status
from starlette.requests import Request

from src.relay.limiter import limiter


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Retrieves the shared connection pool from app state."""
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HTTP client connection pool not initialized",
        )
    return client


def get_client_ip(request: Request) -> str:
    """Resolves the direct socket IP of the caller."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def check_rate_limit(request: Request) -> None:
    """Enforces coarse rate limiting per client IP."""
    client_ip = get_client_ip(request)
    allowed, retry_after = await limiter.is_allowed(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
