from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import Monster


class DummySession:
    def __init__(self):
        self.monsters = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = len(self.monsters) + 1
        self.monsters.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_create_monster_defaults_stats(monkeypatch):
    db = DummySession()
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.post(
        "/content/monster",
        json={
            "name": "Void Stalker",
            "role": "horror",
            "tags": ["space", "predator"],
            "era": "Space",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Void Stalker"
    assert payload["role"] == "horror"
    assert payload["stats"]["hp"] > 0
    assert payload["stats"]["attacks"]
