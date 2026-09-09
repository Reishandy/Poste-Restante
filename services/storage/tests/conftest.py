import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.config import settings

settings.MONGO_DB_NAME = "test_storage_db"
from src.database import get_database
from src.main import app


@pytest.fixture(scope="session")
async def test_app():
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def client(test_app):
    """Client simulating internal OHTTP dispatch (includes dispatch header)."""
    async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
            headers={"X-Internal-Dispatch": test_app.state.internal_dispatch_token},
    ) as ac:
        yield ac


@pytest.fixture
async def external_client(test_app):
    """Client simulating an external caller directly hitting endpoints."""
    async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(autouse=True)
async def clean_database(test_app):
    db = get_database()
    collections = await db.list_collection_names()
    for col in collections:
        if not col.startswith("system."):
            await db[col].delete_many({})
    yield
