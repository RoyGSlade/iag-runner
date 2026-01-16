from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import EntityLink, Secret


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.filters = {}

    def filter(self, expr):
        left = getattr(expr, "left", None)
        right = getattr(expr, "right", None)
        key = getattr(left, "name", None)
        value = getattr(right, "value", None)
        if key is not None:
            self.filters[key] = value
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        results = self.data
        for key, value in self.filters.items():
            results = [item for item in results if getattr(item, key) == value]
        return results


class DummySession:
    def __init__(self):
        self.links = []
        self.secrets = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self, model):
        if model is EntityLink:
            return DummyQuery(self.links)
        if model is Secret:
            return DummyQuery(self.secrets)
        return DummyQuery([])


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_entity_graph_query(monkeypatch):
    db = DummySession()
    db.links = [
        SimpleNamespace(
            id=1,
            from_type="npc",
            from_id=1,
            to_type="faction",
            to_id=10,
            relation="member_of",
            secrecy_level="public",
        ),
        SimpleNamespace(
            id=2,
            from_type="faction",
            from_id=10,
            to_type="npc",
            to_id=2,
            relation="leads",
            secrecy_level="public",
        ),
    ]
    db.secrets = [
        SimpleNamespace(
            id=1,
            owner_type="npc",
            owner_id=1,
            secret_text="Owes Frank a favor.",
            linked_entities_json={"entities": [{"type": "npc", "id": 2}]},
        )
    ]
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.get("/graph/entity/npc/1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity"]["type"] == "npc"
    assert payload["entity"]["id"] == 1
    assert payload["outgoing"][0]["to_type"] == "faction"
    assert payload["incoming"] == []
    assert payload["secrets"][0]["secret_text"] == "Owes Frank a favor."
