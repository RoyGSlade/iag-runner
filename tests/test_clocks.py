from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import Clock, Session as SessionModel


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
        self.clocks = []
        self.session = SimpleNamespace(id=1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = len(self.clocks) + 1
        self.clocks.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def get(self, model, record_id):
        if model is SessionModel:
            return self.session if record_id == self.session.id else None
        if model is Clock:
            for clock in self.clocks:
                if clock.id == record_id:
                    return clock
        return None

    def query(self, model):
        if model is Clock:
            return DummyQuery(self.clocks)
        return DummyQuery([])


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_create_and_advance_clock(monkeypatch):
    db = DummySession()
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.post(
        "/clocks",
        json={
            "session_id": 1,
            "name": "Big Bad Arrival (2 days)",
            "steps_total": 4,
            "visibility": "gm",
            "trigger_tags": ["arrival", "villain"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["steps_done"] == 0
    clock_id = payload["id"]

    response = client.post(f"/clocks/{clock_id}/advance", json={"steps": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["steps_done"] == 1

    response = client.get("/sessions/1/clocks")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["name"] == "Big Bad Arrival (2 days)"
