import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture(scope="session")
async def test_app():
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def client(test_app):
    async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
    ) as ac:
        yield ac
