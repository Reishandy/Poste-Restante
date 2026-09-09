import pytest
from httpx import ASGITransport, AsyncClient
from starlette import status


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("GET", "/mailbox/sample-id", {"headers": {"X-Ownership-Token": "token"}}),
        (
                "PUT",
                "/mailbox/sample-id",
                {"json": {"content": "payload", "token": "token"}},
        ),
        ("DELETE", "/mailbox/sample-id", {"headers": {"X-Ownership-Token": "token"}}),
    ],
)
async def test_direct_mailbox_requests_without_header_return_403(
        external_client, method: str, path: str, kwargs: dict
):
    """Verify any direct HTTP call to /mailbox routes is blocked."""
    response = await external_client.request(method, path, **kwargs)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == (
        "Direct HTTP access forbidden. Access via OHTTP gateway only."
    )


async def test_spoofed_internal_dispatch_header_returns_403(test_app):
    """Verify callers cannot guess or spoof the internal dispatch token."""
    async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"X-Internal-Dispatch": "invalid-or-spoofed-token"},
    ) as client:
        response = await client.get(
            "/mailbox/sample-id",
            headers={"X-Ownership-Token": "token"},
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == (
        "Direct HTTP access forbidden. Access via OHTTP gateway only."
    )


async def test_public_endpoints_unaffected(external_client):
    """Verify non-mailbox endpoints (like the health check) remain open to external calls."""
    response = await external_client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["detail"] == "ok"
