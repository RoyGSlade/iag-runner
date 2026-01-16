from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from rules.core import SessionState, roll, roll_d20
from rules.statuses import apply_status, tick_statuses, total_dex_penalty

CALLED_SHOT_PENALTY = 5
DODGE_BONUS_DEFAULT = 2

CALLED_SHOT_EFFECTS = {
    "disarm": "Target drops a held item on hit.",
    "slow": "Target movement reduced until end of next turn.",
    "stun_attempt": "Target must resist or be Stunned.",
}


@dataclass
class Weapon:
    name: str
    damage: str
    bonus: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class CombatantState:
    name: str
    dex: int
    armor_rating: int
    ap: int
    hp: int
    statuses: dict = field(default_factory=dict)
    skill: int = 0
    attr: int = 0
    attack_bonus: int = 0
    damage_bonus: int = 0
    weapon: Weapon | None = None
    initiative_bonus: int = 0


@dataclass
class CounterResult:
    triggered: bool
    hit: bool
    attack_roll: int
    attack_total: int
    damage: int
    ap_before: int
    ap_after: int
    hp_before: int
    hp_after: int


@dataclass
class AttackResult:
    hit: bool
    crit: bool
    attack_roll: int
    attack_total: int
    target_ar: int
    damage: int
    ap_before: int
    ap_after: int
    hp_before: int
    hp_after: int
    called_shot_effect: str | None
    counter: CounterResult | None


def base_actions() -> dict:
    return {"actions": 1, "reactions": 1}


def roll_initiative(
    session: SessionState,
    combatant: CombatantState,
    *,
    bonus: int = 0,
) -> int:
    effective_dex = combatant.dex - total_dex_penalty(combatant.statuses)
    return roll_d20(session) + effective_dex + combatant.initiative_bonus + bonus


def initiative_order(
    session: SessionState,
    combatants: Iterable[CombatantState],
) -> list[tuple[CombatantState, int]]:
    rolled = [(combatant, roll_initiative(session, combatant)) for combatant in combatants]
    return sorted(rolled, key=lambda item: item[1], reverse=True)


def resolve_attack(
    session: SessionState,
    attacker: CombatantState,
    defender: CombatantState,
    *,
    called_shot: bool = False,
    called_shot_effect: str | None = None,
    reaction: str | None = None,
    reaction_bonus: int = 0,
    reaction_ap: int = 0,
    attack_roll_override: int | None = None,
    counter_roll_override: int | None = None,
) -> tuple[AttackResult, CombatantState, CombatantState]:
    if called_shot and called_shot_effect is None:
        called_shot_effect = "disarm"
    if called_shot and called_shot_effect not in CALLED_SHOT_EFFECTS:
        raise ValueError("Unknown called shot effect.")

    dodge_bonus = _dodge_bonus(reaction, reaction_bonus)
    target_ar = defender.armor_rating + dodge_bonus

    attack_roll = attack_roll_override or roll_d20(session)
    crit = attack_roll >= 19
    attack_total = (
        attack_roll
        + attacker.skill
        + attacker.attr
        + attacker.attack_bonus
        - (CALLED_SHOT_PENALTY if called_shot else 0)
    )
    hit = attack_total >= target_ar

    base_ap = defender.ap
    block_ap = reaction_ap if reaction == "block" else 0
    ap_before = base_ap + block_ap
    hp_before = defender.hp
    ap_after = base_ap
    hp_after = hp_before
    damage_total = 0
    updated_statuses = defender.statuses

    if hit:
        if attacker.weapon is None:
            raise ValueError("Attacker has no weapon for damage roll.")
        damage_total = _roll_damage(
            session,
            attacker.weapon.damage,
            attacker.weapon.bonus + attacker.damage_bonus,
            crit=crit,
        )
        if block_ap:
            ap_after, hp_after = _apply_damage_with_block(
                base_ap, hp_before, damage_total, block_ap
            )
        else:
            ap_after, hp_after = _apply_damage(base_ap, hp_before, damage_total)

        if called_shot:
            updated_statuses = _apply_called_shot_effect(
                defender.statuses, called_shot_effect
            )

    counter_result = None
    if reaction == "counter" and not hit:
        counter_result, attacker = _resolve_counter(
            session,
            counter_roll_override,
            attacker,
            defender,
        )

    result = AttackResult(
        hit=hit,
        crit=crit,
        attack_roll=attack_roll,
        attack_total=attack_total,
        target_ar=target_ar,
        damage=damage_total,
        ap_before=ap_before,
        ap_after=ap_after,
        hp_before=hp_before,
        hp_after=hp_after,
        called_shot_effect=called_shot_effect if hit and called_shot else None,
        counter=counter_result,
    )
    updated_defender = CombatantState(
        **{
            **defender.__dict__,
            "ap": ap_after,
            "hp": hp_after,
            "statuses": updated_statuses,
        }
    )
    return result, attacker, updated_defender


def _dodge_bonus(reaction: str | None, reaction_bonus: int) -> int:
    if reaction != "dodge":
        return 0
    if reaction_bonus:
        return reaction_bonus
    return DODGE_BONUS_DEFAULT


def _roll_damage(
    session: SessionState,
    dice_str: str,
    bonus: int,
    *,
    crit: bool,
) -> int:
    base_total = roll(session, dice_str)
    if session.turn_log:
        last = session.turn_log[-1]
        rolls = last.get("rolls", [])
        modifier = last.get("modifier", 0)
        if isinstance(rolls, list) and all(isinstance(value, int) for value in rolls):
            dice_total = sum(rolls)
            base_total = dice_total * (2 if crit else 1) + int(modifier or 0)
    return base_total + bonus


def _apply_damage(ap: int, hp: int, damage: int) -> tuple[int, int]:
    remaining_ap = max(0, ap - damage)
    damage_to_hp = max(0, damage - ap)
    remaining_hp = max(0, hp - damage_to_hp)
    return remaining_ap, remaining_hp


def _apply_damage_with_block(
    base_ap: int,
    hp: int,
    damage: int,
    block_ap: int,
) -> tuple[int, int]:
    total_ap = base_ap + block_ap
    remaining_ap, remaining_hp = _apply_damage(total_ap, hp, damage)
    remaining_base_ap = min(remaining_ap, base_ap)
    return remaining_base_ap, remaining_hp


def _resolve_counter(
    session: SessionState,
    counter_roll_override: int | None,
    attacker: CombatantState,
    defender: CombatantState,
) -> tuple[CounterResult, CombatantState]:
    counter_weapon = defender.weapon or Weapon(name="Counter Strike", damage="1d4")
    attack_roll = counter_roll_override or roll_d20(session)
    attack_total = (
        attack_roll + defender.skill + defender.attr + defender.attack_bonus
    )
    hit = attack_total >= attacker.armor_rating

    ap_before = attacker.ap
    hp_before = attacker.hp
    ap_after = ap_before
    hp_after = hp_before
    damage_total = 0

    if hit:
        damage_total = _roll_damage(
            session,
            counter_weapon.damage,
            counter_weapon.bonus + defender.damage_bonus,
            crit=attack_roll >= 19,
        )
        ap_after, hp_after = _apply_damage(ap_before, hp_before, damage_total)

    counter_result = CounterResult(
        triggered=True,
        hit=hit,
        attack_roll=attack_roll,
        attack_total=attack_total,
        damage=damage_total,
        ap_before=ap_before,
        ap_after=ap_after,
        hp_before=hp_before,
        hp_after=hp_after,
    )
    updated_attacker = CombatantState(
        **{**attacker.__dict__, "ap": ap_after, "hp": hp_after}
    )
    return counter_result, updated_attacker


def end_turn(
    combatant: CombatantState,
    *,
    tick_type: str = "turn",
) -> tuple[CombatantState, dict]:
    updated_statuses, hp_delta, expired = tick_statuses(
        combatant.statuses, tick_type=tick_type
    )
    updated_hp = max(0, combatant.hp + hp_delta)
    updated = CombatantState(
        **{**combatant.__dict__, "hp": updated_hp, "statuses": updated_statuses}
    )
    return updated, {"hp_delta": hp_delta, "expired": expired}


def _apply_called_shot_effect(statuses: dict, effect: str | None) -> dict:
    if effect == "stun_attempt":
        return apply_status(statuses, "Stun", duration=1)
    if effect == "slow":
        return apply_status(statuses, "Cold", duration=1, level=1)
    return statuses
