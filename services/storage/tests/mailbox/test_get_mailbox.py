from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_get_mailbox_success(client):
    """Happy path: Correct token fetches mailbox content."""
    mailbox_id = "retrieve-mailbox-001"
    token = "owner-token-get"
    content = "some raw content string"

    db = get_database()
    await db["mailboxes"].insert_one(
        {
            "mailbox_id": mailbox_id,
            "content": content,
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(
        f"/mailbox/{mailbox_id}", headers={"X-Ownership-Token": token}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["content"] == content


async def test_get_mailbox_invalid_token_returns_400(client):
    """Security check: Incorrect token returns 400 Bad Request."""
    mailbox_id = "auth-fail-mailbox"
    db = get_database()
    await db["mailboxes"].insert_one(
        {
            "mailbox_id": mailbox_id,
            "content": "secret content",
            "token": "correct-token",
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.get(
        f"/mailbox/{mailbox_id}", headers={"X-Ownership-Token": "wrong-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_get_mailbox_not_found_returns_400(client):
    """Non-existent mailbox query returns 400 Bad Request."""
    response = await client.get(
        "/mailbox/non-existent-id", headers={"X-Ownership-Token": "any-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_get_mailbox_missing_header_returns_422(client):
    """Validation check: Missing X-Ownership-Token header returns 422."""
    response = await client.get("/mailbox/no-header-test")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT