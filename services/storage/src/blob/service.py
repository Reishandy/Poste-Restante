from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import WriteConcern
from pymongo.errors import DuplicateKeyError

COLLECTION_NAME = "blobs"

"""Schema:
{
    "blob_id": str,
    "content": str,
    "created_at": datetime,
}
"""


def _collection(db: AsyncIOMotorDatabase) -> AsyncIOMotorCollection:
    return db[COLLECTION_NAME]


async def get_blob(db: AsyncIOMotorDatabase, blob_id: str) -> str | None:
    result = await _collection(db).find_one(
        {"blob_id": blob_id},
        projection={"content": 1, "_id": 0},
    )
    return result["content"] if result else None


async def store_blob(db: AsyncIOMotorDatabase, blob_id: str, content: str) -> bool:
    try:
        collection = _collection(db).with_options(
            write_concern=WriteConcern(w="majority", j=True)
        )

        result = await collection.insert_one({
            "blob_id": blob_id,
            "content": content,
            "created_at": datetime.now(timezone.utc)
        })

        return result.acknowledged
    except DuplicateKeyError:
        return False


async def delete_blob(db: AsyncIOMotorDatabase, blob_id: str) -> bool:
    result = await _collection(db).delete_one({
        "blob_id": blob_id
    })

    return result.deleted_count == 1
