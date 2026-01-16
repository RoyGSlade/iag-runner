from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from models import Era, Profession, Race, Training


class DummyQuery:
    def __init__(self, data):
        self.data = data

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.data


class DummySession:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self, model):
        return DummyQuery(self.data.get(model, []))


def _patch_session(monkeypatch, data):
    def factory():
        return DummySession(data)

    monkeypatch.setattr("app.main.SessionLocal", factory)


def test_list_eras(monkeypatch):
    _patch_session(
        monkeypatch,
        {
            Era: [
                SimpleNamespace(
                    id=1,
                    name="Space",
                    description="Stars and stations",
                    profile_json={"tags": ["core"]},
                    patch_json=None,
                )
            ]
        },
    )
    client = TestClient(app)
    response = client.get("/eras")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert set(payload[0].keys()) >= {"id", "name", "description", "is_canonical"}


def test_list_races(monkeypatch):
    _patch_session(
        monkeypatch,
        {
            Race: [
                SimpleNamespace(
                    id=1,
                    name="Android",
                    description="Synthetic",
                    attributes_json={"attributeBonus": {"intelligence": 2}},
                )
            ]
        },
    )
    client = TestClient(app)
    response = client.get("/races")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert set(payload[0].keys()) >= {"id", "name", "short_desc", "attribute_bonus"}


def test_list_trainings(monkeypatch):
    _patch_session(
        monkeypatch,
        {
            Training: [
                SimpleNamespace(
                    id=1,
                    name="Aviator School",
                    description="Pilot training",
                    skill_levels_json={"initiative": 1, "majors": [{"name": "Control"}]},
                )
            ]
        },
    )
    client = TestClient(app)
    response = client.get("/trainings")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert set(payload[0].keys()) >= {"id", "name", "short_desc", "bonuses"}


def test_list_professions(monkeypatch):
    _patch_session(
        monkeypatch,
        {
            Profession: [
                SimpleNamespace(
                    id=1,
                    name="Bounty Hunter",
                    description="Tracks targets",
                    attributes_json={"startingCredits": 15000},
                )
            ]
        },
    )
    client = TestClient(app)
    response = client.get("/professions")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert set(payload[0].keys()) >= {"id", "name", "short_desc", "starting_credits"}
