from __future__ import annotations

from dataclasses import dataclass

from llm.schemas import GMPlan, GMPlanStep


@dataclass(frozen=True)
class EngineAction:
    type: str
    payload: dict


@dataclass(frozen=True)
class CompileResult:
    actions: list[EngineAction]
    needs_clarification: bool
    ooc_questions: list[str]
    dev_report: dict | None


def compile_plan(plan: GMPlan, *, dev_mode: bool = False) -> CompileResult:
    actions: list[EngineAction] = []
    unmappable: list[str] = []

    for step in plan.root:
        action = _map_step(step)
        if action is None:
            unmappable.append(step.type)
        else:
            actions.append(action)

    if unmappable:
        if dev_mode:
            return CompileResult(
                actions=[],
                needs_clarification=True,
                ooc_questions=[],
                dev_report={"needs_new_tool": unmappable},
            )
        return CompileResult(
            actions=[],
            needs_clarification=True,
            ooc_questions=["That action is not supported yet. What should happen?"],
            dev_report=None,
        )

    return CompileResult(
        actions=actions,
        needs_clarification=False,
        ooc_questions=[],
        dev_report=None,
    )


def _map_step(step: GMPlanStep) -> EngineAction | None:
    if step.type == "attack":
        return EngineAction(
            type="combat.attack",
            payload={
                "actor_id": step.actor_id,
                "targets": step.targets,
                "skill_used": step.skill_used,
                "notes": step.notes,
            },
        )
    if step.type == "use_power":
        return EngineAction(
            type="powers.use",
            payload={
                "actor_id": step.actor_id,
                "power_used": step.power_used,
                "targets": step.targets,
                "notes": step.notes,
            },
        )
    if step.type in {"craft", "improvise"}:
        return EngineAction(
            type="project.create",
            payload={
                "actor_id": step.actor_id,
                "kind": step.type,
                "notes": step.notes,
            },
        )
    if step.type in {"investigate", "social"}:
        return EngineAction(
            type="check.request",
            payload={
                "actor_id": step.actor_id,
                "targets": step.targets,
                "skill_used": step.skill_used,
                "time_cost": step.time_cost,
                "risk_level": step.risk_level,
                "notes": step.notes,
            },
        )
    return None
