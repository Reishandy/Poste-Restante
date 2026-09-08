from starlette import status
from src.database import get_database


async def test_store_blob_success(client):
    """Happy path: Storing a new blob returns 201 and persists data to Mongo."""
    payload = {"content": "durable storage payload"}
    blob_id = "test-blob-001"

    response = await client.put(f"/blob/{blob_id}", json=payload)

    assert response.status_code == status.HTTP_201_CREATED

    db = get_database()
    stored = await db["blobs"].find_one({"blob_id": blob_id})
    assert stored is not None
    assert stored["content"] == payload["content"]
    assert stored["created_at"] is not None


async def test_store_blob_duplicate_id_returns_400(client):
    """Idempotency check: Storing the same blob_id twice returns 400."""
    payload = {"content": "initial payload"}
    blob_id = "duplicate-test-blob"

    res1 = await client.put(f"/blob/{blob_id}", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    # Second write with same ID should fail
    res2 = await client.put(f"/blob/{blob_id}", json={"content": "updated payload"})
    assert res2.status_code == status.HTTP_400_BAD_REQUEST

    # Ensure the original content was not overwritten
    db = get_database()
    doc = await db["blobs"].find_one({"blob_id": blob_id})
    assert doc["content"] == "initial payload"


async def test_store_blob_missing_body_returns_422(client):
    """Validation check: Missing required JSON body returns 422 Unprocessable Entity."""
    response = await client.put("/blob/invalid-body", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT