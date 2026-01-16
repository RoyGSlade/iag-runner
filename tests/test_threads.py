from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import Session as SessionModel, Thread


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
        self.threads = []
        self.session = SimpleNamespace(id=1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = len(self.threads) + 1
        self.threads.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def get(self, model, record_id):
        if model is SessionModel:
            return self.session if record_id == self.session.id else None
        if model is Thread:
            for thread in self.threads:
                if thread.id == record_id:
                    return thread
        return None

    def query(self, model):
        if model is Thread:
            return DummyQuery(self.threads)
        return DummyQuery([])


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_list_and_resolve_threads(monkeypatch):
    db = DummySession()
    db.add(
        Thread(
            session_id=1,
            type="hook",
            status="open",
            urgency="med",
            visibility="player",
            related_entities_json={"npcs": [1]},
            text="A coded message circulates.",
        )
    )
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.get("/sessions/1/threads")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    item = records[0]
    assert item["type"] == "hook"
    assert item["status"] == "open"
    assert item["urgency"] == "med"
    assert item["visibility"] == "player"
    assert item["related_entities"] == {"npcs": [1]}
    assert item["text"] == "A coded message circulates."

    response = client.post("/threads/1/resolve", json={"status": "resolved"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
