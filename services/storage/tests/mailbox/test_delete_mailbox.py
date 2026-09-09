from datetime import datetime, timezone
from starlette import status
from src.database import get_database


async def test_delete_mailbox_success(client):
    """Happy path: Deleting with valid token returns 200 and removes document."""
    mailbox_id = "delete-target-mailbox"
    token = "owner-token-delete"

    db = get_database()
    await db["mailboxes"].insert_one(
        {
            "mailbox_id": mailbox_id,
            "content": "to be deleted",
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.delete(
        f"/mailbox/{mailbox_id}", headers={"X-Ownership-Token": token}
    )
    assert response.status_code == status.HTTP_200_OK

    doc = await db["mailboxes"].find_one({"mailbox_id": mailbox_id})
    assert doc is None


async def test_delete_mailbox_invalid_token_returns_400(client):
    """Security check: Deleting with invalid token returns 400 and preserves doc."""
    mailbox_id = "protected-mailbox"
    token = "keep-safe"

    db = get_database()
    await db["mailboxes"].insert_one(
        {
            "mailbox_id": mailbox_id,
            "content": "must stay",
            "token": token,
            "created_at": datetime.now(timezone.utc),
        }
    )

    response = await client.delete(
        f"/mailbox/{mailbox_id}", headers={"X-Ownership-Token": "bad-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    doc = await db["mailboxes"].find_one({"mailbox_id": mailbox_id})
    assert doc is not None


async def test_delete_mailbox_non_existent_returns_400(client):
    """Deleting a non-existent mailbox returns 400 Bad Request."""
    response = await client.delete(
        "/mailbox/does-not-exist", headers={"X-Ownership-Token": "dummy-token"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_delete_mailbox_missing_header_returns_422(client):
    """Validation check: Missing X-Ownership-Token header returns 422."""
    response = await client.delete("/mailbox/no-header-test")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT