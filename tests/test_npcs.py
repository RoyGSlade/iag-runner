from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import NPC, Session as SessionModel


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.session_id = None

    def filter(self, *args, **kwargs):
        if args:
            expr = args[0]
            right = getattr(expr, "right", None)
            value = getattr(right, "value", None)
            if value is not None:
                self.session_id = value
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        if self.session_id is None:
            return self.data
        return [item for item in self.data if item.session_id == self.session_id]


class DummySession:
    def __init__(self):
        self.npcs = []
        self.session = SimpleNamespace(id=1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = len(self.npcs) + 1
        self.npcs.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def get(self, model, record_id):
        if model is SessionModel:
            return self.session if record_id == self.session.id else None
        return None

    def query(self, model):
        if model is NPC:
            return DummyQuery(self.npcs)
        return DummyQuery([])


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_create_and_list_npcs(monkeypatch):
    db = DummySession()
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.post(
        "/content/npc",
        json={
            "session_id": 1,
            "name": "Dockmaster Ryn",
            "role": "quartermaster",
            "personality": {"traits": ["gruff", "loyal"]},
            "goals": {"short_term": "keep shipments moving"},
            "fears": {"primary": "losing the station"},
            "secrets": {"gm_only": "owes a debt"},
            "relationships": {"links": [{"id": 2, "relation": "rival"}]},
            "stats": {"hp": 4, "ar": 10},
            "voice": {"tags": ["raspy", "direct"]},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Dockmaster Ryn"
    assert payload["role"] == "quartermaster"

    response = client.get("/sessions/1/npcs")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["name"] == "Dockmaster Ryn"
