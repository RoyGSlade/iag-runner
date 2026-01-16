from fastapi.testclient import TestClient

from app.main import app
from models import Location, Scene


class DummySession:
    def __init__(self):
        self.locations = []
        self.scenes = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if isinstance(obj, Location):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.locations) + 1
            self.locations.append(obj)
        elif isinstance(obj, Scene):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.scenes) + 1
            self.scenes.append(obj)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_location_bootstrap_card_defaults(monkeypatch):
    db = DummySession()
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.post(
        "/content/location_bootstrap",
        json={"name": "Dustfall", "era": "Space"},
    )
    assert response.status_code == 200
    payload = response.json()
    card = payload["location"]["card"]
    assert card["authority"]
    assert card["economy"]
    assert card["danger"]
    assert card["secret"]
    assert isinstance(card["hooks"], list)
