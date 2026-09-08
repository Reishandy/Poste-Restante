from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.config import settings


class Database:
    """Thin wrapper holding the Motor client/db for the app's lifetime."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB_NAME]

        await self.client.admin.command("ping")

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()

    async def create_indexes(self):
        """Creates or updates necessary indexes for the collections."""
        collection = self.client[settings.MONGO_DB_NAME]["blobs"]
        await collection.create_index("blob_id", unique=True)

        existing_indexes = await collection.index_information()
        ttl_index = existing_indexes.get("created_at_1")

        # If the index exists with different TTL options, drop it first
        if ttl_index and ttl_index.get("expireAfterSeconds") != settings.BLOB_EXPIRY_SECONDS:
            await collection.drop_index("created_at_1")

        await collection.create_index(
            "created_at",
            expireAfterSeconds=settings.BLOB_EXPIRY_SECONDS,
        )


database = Database()


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to grab the active DB handle in routes/services."""
    assert database.db is not None, "Database is not connected"
    return database.db
