from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_get_blob_success(client):
    """Happy path: Correct token fetches blob content."""
    blob_id = "retrieve-blob-001"
    token = "owner-token-get"
    content = "some raw content string"

    db = get_database()
    await db["blobs"].insert_one(
        {
            "blob_id": blob_id,
            "content": content,
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(
        f"/blob/{blob_id}", headers={"X-Ownership-Token": token}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["content"] == content


async def test_get_blob_invalid_token_returns_400(client):
    """Security check: Incorrect token returns 400 Bad Request."""
    blob_id = "auth-fail-blob"
    db = get_database()
    await db["blobs"].insert_one(
        {
            "blob_id": blob_id,
            "content": "secret content",
            "token": "correct-token",
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(
        f"/blob/{blob_id}", headers={"X-Ownership-Token": "wrong-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_get_blob_not_found_returns_400(client):
    """Non-existent blob query returns 400 Bad Request."""
    response = await client.get(
        "/blob/non-existent-id", headers={"X-Ownership-Token": "any-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_get_blob_missing_header_returns_422(client):
    """Validation check: Missing X-Ownership-Token header returns 422."""
    response = await client.get("/blob/no-header-test")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT