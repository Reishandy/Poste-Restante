from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_delete_blob_success(client):
    """Happy path: Deleting an existing blob returns 200 and removes it from Mongo."""
    blob_id = "delete-target-blob"

    db = get_database()
    await db["blobs"].insert_one({
        "blob_id": blob_id,
        "content": "to be deleted",
        "created_at": datetime.now(timezone.utc),
    })

    response = await client.delete(f"/blob/{blob_id}")

    assert response.status_code == status.HTTP_200_OK

    doc = await db["blobs"].find_one({"blob_id": blob_id})
    assert doc is None


async def test_delete_blob_non_existent_returns_400(client):
    """Deleting a non-existent blob returns 400 Bad Request."""
    response = await client.delete("/blob/does-not-exist")
    assert response.status_code == status.HTTP_400_BAD_REQUEST