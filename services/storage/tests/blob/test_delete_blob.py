from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_delete_blob_success(client):
    """Happy path: Deleting with valid token returns 200 and removes document."""
    blob_id = "delete-target-blob"
    token = "owner-token-delete"

    db = get_database()
    await db["blobs"].insert_one(
        {
            "blob_id": blob_id,
            "content": "to be deleted",
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.delete(
        f"/blob/{blob_id}", headers={"X-Ownership-Token": token}
    )
    assert response.status_code == status.HTTP_200_OK

    doc = await db["blobs"].find_one({"blob_id": blob_id})
    assert doc is None


async def test_delete_blob_invalid_token_returns_400(client):
    """Security check: Deleting with invalid token returns 400 and preserves doc."""
    blob_id = "protected-blob"
    token = "keep-safe"

    db = get_database()
    await db["blobs"].insert_one(
        {
            "blob_id": blob_id,
            "content": "must stay",
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.delete(
        f"/blob/{blob_id}", headers={"X-Ownership-Token": "bad-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    doc = await db["blobs"].find_one({"blob_id": blob_id})
    assert doc is not None


async def test_delete_blob_non_existent_returns_400(client):
    """Deleting a non-existent blob returns 400 Bad Request."""
    response = await client.delete(
        "/blob/does-not-exist", headers={"X-Ownership-Token": "dummy-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_delete_blob_missing_header_returns_422(client):
    """Validation check: Missing X-Ownership-Token header returns 422."""
    response = await client.delete("/blob/no-header-test")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT