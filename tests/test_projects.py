from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import Project, Session as SessionModel


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
        self.projects = []
        self.session = SimpleNamespace(id=1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = len(self.projects) + 1
        self.projects.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def get(self, model, record_id):
        if model is SessionModel:
            return self.session if record_id == self.session.id else None
        if model is Project:
            for project in self.projects:
                if project.id == record_id:
                    return project
        return None

    def query(self, model):
        if model is Project:
            return DummyQuery(self.projects)
        return DummyQuery([])


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_create_and_advance_project(monkeypatch):
    db = DummySession()
    _patch_session(monkeypatch, db)
    client = TestClient(app)

    response = client.post(
        "/projects",
        json={
            "session_id": 1,
            "name": "Forge a plasma edge",
            "type": "craft",
            "requirements": {"materials": ["alloy", "plasma core"]},
            "constraints": {"size": "small"},
            "work_units_total": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["work_units_done"] == 0
    project_id = payload["id"]

    response = client.post(f"/projects/{project_id}/advance", json={"work_units": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["work_units_done"] == 2
    assert payload["status"] == "active"

    response = client.post(f"/projects/{project_id}/advance", json={"work_units": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["work_units_done"] == 5
    assert payload["status"] == "completed"

    response = client.get("/sessions/1/projects")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["name"] == "Forge a plasma edge"
