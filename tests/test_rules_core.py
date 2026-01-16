from rules.core import SessionState, roll, roll_d20


def test_deterministic_rolls_with_seed() -> None:
    first = SessionState(seed=1234)
    second = SessionState(seed=1234)

    assert roll_d20(first) == roll_d20(second)
    assert roll(first, "2d6+3") == roll(second, "2d6+3")
    assert roll(first, "1d8-1") == roll(second, "1d8-1")


def test_roll_logging() -> None:
    session = SessionState(seed=42)

    d20_result = roll_d20(session, label="initiative")
    dice_result = roll(session, "2d4+1", label="damage")

    assert len(session.turn_log) == 2
    first = session.turn_log[0]
    second = session.turn_log[1]

    assert first["formula"] == "1d20"
    assert first["result"] == d20_result
    assert first["label"] == "initiative"

    assert second["formula"] == "2d4+1"
    assert second["result"] == dice_result
    assert second["label"] == "damage"
