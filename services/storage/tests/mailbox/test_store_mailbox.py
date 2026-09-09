import pytest
from src.mailbox.dependenies import solve_pow
from starlette import status

from src.config import settings
from src.database import get_database


@pytest.fixture(autouse=True)
def lower_pow_difficulty(monkeypatch):
    """Keep PoW difficulty low so tests compute nonces in microseconds."""
    monkeypatch.setattr(settings, "POW_DIFFICULTY_BITS", 8)


async def test_store_mailbox_success(client):
    """Happy path: Storing a new mailbox with token and valid PoW returns 201."""
    payload = {"content": "durable storage payload", "token": "secret-token-123"}
    mailbox_id = "test-mailbox-001"
    nonce = solve_pow(mailbox_id)

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce},
    )
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
    nonce = solve_pow(mailbox_id)

    res1 = await client.put(
        f"/mailbox/{mailbox_id}",
        json=payload,
        headers={"X-PoW-Nonce": nonce},
    )
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = await client.put(
        f"/mailbox/{mailbox_id}",
        json={"content": "updated", "token": "token-b"},
        headers={"X-PoW-Nonce": nonce},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST

    db = get_database()
    doc = await db["mailboxes"].find_one({"mailbox_id": mailbox_id})
    assert doc["content"] == "initial payload"


async def test_store_mailbox_missing_token_returns_422(client):
    """Validation check: Missing token field in body returns 422."""
    mailbox_id = "missing-token-mailbox"
    nonce = solve_pow(mailbox_id)

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json={"content": "only-content"},
        headers={"X-PoW-Nonce": nonce},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_store_mailbox_missing_body_returns_422(client):
    """Validation check: Missing required JSON body returns 422."""
    mailbox_id = "invalid-body-mailbox"
    nonce = solve_pow(mailbox_id)

    response = await client.put(
        f"/mailbox/{mailbox_id}",
        json={},
        headers={"X-PoW-Nonce": nonce},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
