from starlette import status

from src.database import get_database


async def test_store_mailbox_success(client):
    """Happy path: Storing a new mailbox with token returns 201 and persists to Mongo."""
    payload = {"content": "durable storage payload", "token": "secret-token-123"}
    mailbox_id = "test-mailbox-001"

    response = await client.put(f"/mailbox/{mailbox_id}", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    db = get_database()
    stored = await db["mailboxes"].find_one({"mailbox_id": mailbox_id})
    assert stored is not None
    assert stored["content"] == payload["content"]
    assert stored["token"] == payload["token"]
    assert stored["created_at"] is not None


async def test_store_mailbox_duplicate_id_returns_400(client):
    """Idempotency check: Storing the same mailbox_id twice returns 400."""
    payload = {"content": "initial payload", "token": "token-a"}
    mailbox_id = "duplicate-test-mailbox"

    res1 = await client.put(f"/mailbox/{mailbox_id}", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = await client.put(
        f"/mailbox/{mailbox_id}", json={"content": "updated", "token": "token-b"}
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST

    db = get_database()
    doc = await db["mailboxes"].find_one({"mailbox_id": mailbox_id})
    assert doc["content"] == "initial payload"


async def test_store_mailbox_missing_token_returns_422(client):
    """Validation check: Missing token field in body returns 422."""
    response = await client.put(
        "/mailbox/missing-token", json={"content": "only-content"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_store_mailbox_missing_body_returns_422(client):
    """Validation check: Missing required JSON body returns 422."""
    response = await client.put("/mailbox/invalid-body", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
