from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Iterable

DICE_PATTERN = re.compile(r"^\s*(\d*)d(\d+)([+-]\d+)?\s*$", re.IGNORECASE)
INTEGER_PATTERN = re.compile(r"^\s*\d+\s*$")


@dataclass
class SessionState:
    seed: int
    turn_log: list[dict] = field(default_factory=list)
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)


def _log_roll(
    session: SessionState,
    *,
    formula: str,
    result: int,
    rolls: Iterable[int],
    modifier: int,
    label: str | None,
) -> None:
    session.turn_log.append(
        {
            "formula": formula,
            "result": result,
            "rolls": list(rolls),
            "modifier": modifier,
            "label": label,
        }
    )


def roll_d20(session: SessionState, *, label: str | None = None) -> int:
    result = session.rng.randint(1, 20)
    _log_roll(
        session,
        formula="1d20",
        result=result,
        rolls=[result],
        modifier=0,
        label=label,
    )
    return result


def roll(session: SessionState, dice_str: str, *, label: str | None = None) -> int:
    if INTEGER_PATTERN.match(dice_str):
        result = int(dice_str)
        _log_roll(
            session,
            formula=str(result),
            result=result,
            rolls=[],
            modifier=0,
            label=label,
        )
        return result

    match = DICE_PATTERN.match(dice_str)
    if not match:
        raise ValueError(f"Invalid dice string: {dice_str}")

    count_text, sides_text, modifier_text = match.groups()
    count = int(count_text) if count_text else 1
    sides = int(sides_text)
    modifier = int(modifier_text) if modifier_text else 0

    if count <= 0 or sides <= 0:
        raise ValueError(f"Invalid dice string: {dice_str}")

    rolls = [session.rng.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    _log_roll(
        session,
        formula=dice_str.strip(),
        result=total,
        rolls=rolls,
        modifier=modifier,
        label=label,
    )
    return total
