from fastapi import HTTPException
from starlette import status
from starlette.requests import Request


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Retrieves the shared connection pool from app state."""
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HTTP client connection pool not initialized",
        )
    return client
