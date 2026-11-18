import pytest
from fastapi.testclient import TestClient

from app.bookstore import Bookstore
from app.main import app, get_store


@pytest.fixture
def client():
    """TestClient з чистим сховищем для кожного тесту."""
    store = Bookstore()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_book(client):
    """Фабрика: створює книгу через API і повертає JSON-відповідь."""
    counter = iter(range(1, 10_000))

    def _make(**overrides):
        payload = {
            "isbn": f"978000000{next(counter):04d}",
            "title": "Test Book",
            "author": "Test Author",
            "price": 100.0,
            "quantity": 10,
            "description": "",
        }
        payload.update(overrides)
        resp = client.post("/books/", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
