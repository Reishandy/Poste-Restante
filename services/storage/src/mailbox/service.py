import secrets
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import WriteConcern
from pymongo.errors import DuplicateKeyError

COLLECTION_NAME = "mailboxes"

"""Schema:
{
    "mailbox_id": str,
    "content": str,
    "created_at": datetime,
}
"""


def _collection(db: AsyncIOMotorDatabase) -> AsyncIOMotorCollection:
    return db[COLLECTION_NAME]


async def get_mailbox(
        db: AsyncIOMotorDatabase,
        mailbox_id: str,
        token: str
) -> str | None:
    result = await _collection(db).find_one(
        {"mailbox_id": mailbox_id},
        projection={"content": 1, "token": 1, "_id": 0},
    )
    if not result:
        return None

    stored_token = result.get("token", "")
    if not secrets.compare_digest(stored_token, token):
        return None

    return result["content"]


async def store_mailbox(
        db: AsyncIOMotorDatabase,
        mailbox_id: str,
        content: str,
        token: str
) -> bool:
    try:
        collection = _collection(db).with_options(
            write_concern=WriteConcern(w="majority", j=True)
        )
        result = await collection.insert_one(
            {
                "mailbox_id": mailbox_id,
                "content": content,
                "token": token,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return result.acknowledged
    except DuplicateKeyError:
        return False


async def delete_mailbox(
        db: AsyncIOMotorDatabase,
        mailbox_id: str,
        token: str
) -> bool:
    result = await _collection(db).find_one(
        {"mailbox_id": mailbox_id},
        projection={"token": 1, "_id": 0},
    )
    if not result:
        return False

    stored_token = result.get("token", "")
    if not secrets.compare_digest(stored_token, token):
        return False

    delete_result = await _collection(db).delete_one({"mailbox_id": mailbox_id})
    return delete_result.deleted_count == 1
