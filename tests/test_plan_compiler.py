from llm.schemas import GMPlan
from gm_os.plan_compiler import compile_plan


def test_attack_maps_to_engine_action() -> None:
    plan = GMPlan.model_validate(
        [
            {
                "type": "attack",
                "actor_id": 1,
                "targets": ["nearest_threat"],
                "skill_used": "Melee",
                "power_used": None,
                "time_cost": "action",
                "risk_level": "high",
                "notes": "Strike fast.",
            }
        ]
    )
    result = compile_plan(plan, dev_mode=False)
    assert result.needs_clarification is False
    assert len(result.actions) == 1
    assert result.actions[0].type == "combat.attack"


def test_unmappable_step_routes_to_clarification() -> None:
    plan = GMPlan.model_validate(
        [
            {
                "type": "downtime",
                "actor_id": 1,
                "targets": ["home"],
                "skill_used": None,
                "power_used": None,
                "time_cost": "hours",
                "risk_level": "low",
                "notes": "Rest up.",
            }
        ]
    )
    result = compile_plan(plan, dev_mode=False)
    assert result.needs_clarification is True
    assert result.actions == []
    assert result.ooc_questions


def test_unmappable_step_dev_report() -> None:
    plan = GMPlan.model_validate(
        [
            {
                "type": "downtime",
                "actor_id": 1,
                "targets": ["home"],
                "skill_used": None,
                "power_used": None,
                "time_cost": "hours",
                "risk_level": "low",
                "notes": "Rest up.",
            }
        ]
    )
    result = compile_plan(plan, dev_mode=True)
    assert result.needs_clarification is True
    assert result.actions == []
    assert result.dev_report is not None
