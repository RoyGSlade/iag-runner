from types import SimpleNamespace

from gm_os.director import director_tick
from models import Clock, PlayerProfile, Session as SessionModel, Thread


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.session_id = None

    def filter(self, expr):
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
        return [item for item in self.data if getattr(item, "session_id", None) == self.session_id]

    def first(self):
        records = self.all()
        return records[0] if records else None


class DummySession:
    def __init__(self, session):
        self.session = session
        self.clocks = []
        self.threads = []
        self.profile = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, record_id):
        if model is SessionModel and record_id == self.session.id:
            return self.session
        return None

    def query(self, model):
        if model is Clock:
            return DummyQuery(self.clocks)
        if model is PlayerProfile:
            return DummyQuery([self.profile] if self.profile else [])
        return DummyQuery([])

    def add(self, obj):
        if isinstance(obj, Thread):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.threads) + 1
            self.threads.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("gm_os.director.SessionLocal", factory)


def test_director_tick_advances_clocks_and_creates_thread(monkeypatch):
    session = SimpleNamespace(id=1, rng_seed=10, metadata_json={})
    db = DummySession(session)
    db.profile = PlayerProfile(
        session_id=1,
        interests_json={
            "combat": {"count": 0, "weight": 0.0},
            "crafting": {"count": 0, "weight": 0.0},
            "mystery": {"count": 0, "weight": 0.0},
            "politics": {"count": 0, "weight": 0.0},
            "horror": {"count": 0, "weight": 0.0},
            "exploration": {"count": 0, "weight": 0.0},
        },
        themes_json={"avoid": []},
    )
    db.clocks.append(
        SimpleNamespace(id=1, session_id=1, steps_total=4, steps_done=0)
    )
    _patch_session(monkeypatch, db)

    result = director_tick(1, "travel")

    assert result.thread_id == 1
    assert db.clocks[0].steps_done == 2
    assert len(db.threads) == 1
    assert session.metadata_json.get("director_index") == 1


def test_director_tick_respects_profile_weights(monkeypatch):
    session = SimpleNamespace(id=1, rng_seed=3, metadata_json={})
    db = DummySession(session)
    db.profile = PlayerProfile(
        session_id=1,
        interests_json={
            "combat": {"count": 0, "weight": 5.0},
            "crafting": {"count": 0, "weight": 0.0},
            "mystery": {"count": 0, "weight": 0.0},
            "politics": {"count": 0, "weight": 0.0},
            "horror": {"count": 0, "weight": 0.0},
            "exploration": {"count": 0, "weight": 0.0},
        },
        themes_json={"avoid": []},
    )
    _patch_session(monkeypatch, db)

    first = director_tick(1, "turn")

    session_alt = SimpleNamespace(id=2, rng_seed=3, metadata_json={})
    db_alt = DummySession(session_alt)
    db_alt.profile = PlayerProfile(
        session_id=2,
        interests_json={
            "combat": {"count": 0, "weight": 0.0},
            "crafting": {"count": 0, "weight": 0.0},
            "mystery": {"count": 0, "weight": 5.0},
            "politics": {"count": 0, "weight": 0.0},
            "horror": {"count": 0, "weight": 0.0},
            "exploration": {"count": 0, "weight": 0.0},
        },
        themes_json={"avoid": []},
    )
    _patch_session(monkeypatch, db_alt)

    second = director_tick(2, "turn")

    assert first.event is not None
    assert second.event is not None
    assert first.event.get("type") != second.event.get("type")
