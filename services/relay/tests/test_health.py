from starlette import status

from src.config import settings


async def test_health_check_operational(client):
    """Verify relay health check returns 200 OK with proper payload schema."""
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert payload["detail"] == "ok"
    assert payload["app"] == settings.APP_NAME
    assert payload["service"] == "relay"
    assert payload["version"] == settings.APP_VERSION
