from types import SimpleNamespace

from gm_os.memory import promote_memories
from models import MemoryCard, Project, Session as SessionModel


class DummyQuery:
    def __init__(self, data):
        self.data = data
        self.filters = []

    def filter(self, *args, **kwargs):
        if args:
            self.filters.extend(args)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._apply()

    def first(self):
        results = self._apply()
        return results[0] if results else None

    def _apply(self):
        results = list(self.data)
        for expr in self.filters:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            field = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if field is not None:
                results = [item for item in results if getattr(item, field) == value]
        return results


class DummySession:
    def __init__(self, session):
        self.session = session
        self.memory_cards = []
        self.projects = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, record_id):
        if model is SessionModel and record_id == self.session.id:
            return self.session
        return None

    def query(self, model):
        if model is MemoryCard:
            return DummyQuery(self.memory_cards)
        if model is Project:
            return DummyQuery(self.projects)
        return DummyQuery([])

    def add(self, obj):
        if isinstance(obj, MemoryCard):
            if getattr(obj, "id", None) is None:
                obj.id = len(self.memory_cards) + 1
            self.memory_cards.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None


def _patch_session(monkeypatch, db):
    def factory():
        return db

    monkeypatch.setattr("gm_os.memory.SessionLocal", factory)


def _build_turn_log(count: int) -> list[dict]:
    log = []
    for idx in range(count):
        log.append(
            {
                "action": "attack",
                "power": None,
                "item": None,
                "rolls": [],
                "outcome": {"hit": True, "damage": idx},
            }
        )
    return log


def test_promote_memories_compacts_and_preserves_facts(monkeypatch):
    session = SimpleNamespace(
        id=1,
        metadata_json={
            "location": "Fallon Station",
            "turn_log": _build_turn_log(100),
        },
    )
    db = DummySession(session)
    _patch_session(monkeypatch, db)

    updated = promote_memories(1, turn_count_threshold=100)

    assert updated is True
    metadata = session.metadata_json
    assert len(metadata["turn_log"]) == 30
    assert len(metadata["recent_summary"]) == 30
    assert "damage=69" in (metadata.get("rolling_summary") or "")
    assert any("damage=99" in fact for fact in metadata["recent_summary"])
    assert len(db.memory_cards) == 1
    assert db.memory_cards[0].entity_type == "location"
