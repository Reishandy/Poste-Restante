import pytest
from starlette import status

from src.config import settings
from src.relay.limiter import limiter


@pytest.fixture(autouse=True)
def clean_limiter():
    limiter.reset()
    yield
    limiter.reset()


async def test_relay_enforces_per_ip_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 3)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 10)

    # First 3 requests evaluate rate check (they fail with 400 for empty body, which is past rate checking)
    for _ in range(3):
        res = await client.post(
            "/relay",
            content=b"",
            headers={
                "content-type": "message/ohttp-req",
                "Target-URI": "http://storage.internal/ohttp",
            },
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # 4th request must be rejected with 429
    blocked_res = await client.post(
        "/relay",
        content=b"sample-payload",
        headers={
            "content-type": "message/ohttp-req",
            "Target-URI": "http://storage.internal/ohttp",
        },
    )
    assert blocked_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked_res.json()["detail"] == "Rate limit exceeded. Try again later."
    assert "Retry-After" in blocked_res.headers
    assert int(blocked_res.headers["Retry-After"]) > 0