from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_get_blob_success(client):
    """Happy path: Seed a document directly into Mongo and verify GET fetches it."""
    blob_id = "retrieve-blob-001"
    expected_content = "some raw content string"

    db = get_database()
    await db["blobs"].insert_one({
        "blob_id": blob_id,
        "content": expected_content,
        "created_at": datetime.now(timezone.utc),
    })

    response = await client.get(f"/blob/{blob_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["content"] == expected_content


async def test_get_blob_not_found_returns_400(client):
    """Non-existent blob query returns 400 Bad Request."""
    response = await client.get("/blob/non-existent-id")
    assert response.status_code == status.HTTP_400_BAD_REQUEST