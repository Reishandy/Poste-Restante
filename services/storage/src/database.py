from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings


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


database = Database()


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to grab the active DB handle in routes/services."""
    assert database.db is not None, "Database is not connected"
    return database.db
