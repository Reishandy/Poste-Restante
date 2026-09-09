import base64
from unittest.mock import AsyncMock, MagicMock

from starlette import status

from src.config import settings
from src.database import get_database
from src.hpke.keys import SUITE
from src.main import app


async def test_health_check_operational(client):
    """Happy path: DB is running, endpoint returns 200."""
    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["service"] == settings.APP_NAME
    assert payload["database"] == "ok"
    assert payload["detail"] == "ok"


async def test_health_check_degraded_when_ping_fails(client):
    """Degraded path: DB command raises error, endpoint returns 503."""
    # Create a mock database whose admin ping command fails
    broken_db = MagicMock()
    broken_db.client.admin.command = AsyncMock(
        side_effect=ConnectionError("Database unavailable")
    )

    # Temporarily override get_database
    app.dependency_overrides[get_database] = lambda: broken_db
    try:
        response = await client.get("/")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        payload = response.json()
        assert payload["database"] == "Unreachable"
        assert payload["detail"] == "Degraded"
    finally:
        app.dependency_overrides.clear()


async def test_health_check_returns_valid_hpke_public_key(client):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK

    b64_key = response.json().get("hpke_public_key")
    assert b64_key is not None

    raw_pub = base64.b64decode(b64_key)
    assert len(raw_pub) == 32

    # Must deserialize without raising an exception
    key_obj = SUITE.kem.deserialize_public_key(raw_pub)
    assert key_obj is not None
