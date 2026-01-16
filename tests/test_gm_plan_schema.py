import pytest
from pydantic import ValidationError

from llm.schemas import GMPlan


def test_gm_plan_parses() -> None:
    plan = GMPlan.model_validate(
        [
            {
                "type": "move",
                "actor_id": 1,
                "targets": ["platform edge"],
                "skill_used": None,
                "power_used": None,
                "time_cost": "action",
                "risk_level": "med",
                "notes": "Advance to cover.",
            },
            {
                "type": "attack",
                "actor_id": 1,
                "targets": ["nearest_threat"],
                "skill_used": "Melee",
                "power_used": None,
                "time_cost": "action",
                "risk_level": "high",
                "notes": "Strike fast.",
            },
        ]
    )
    assert len(plan.root) == 2
    assert plan.root[0].type == "move"


def test_gm_plan_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GMPlan.model_validate(
            [
                {
                    "type": "social",
                    "actor_id": 2,
                    "targets": ["dockmaster"],
                    "skill_used": "Persuasion",
                    "power_used": None,
                    "time_cost": "minutes",
                    "risk_level": "low",
                    "notes": "Ask for help.",
                    "extra": True,
                }
            ]
        )
