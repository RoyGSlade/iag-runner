from rules.combat import CombatantState, Weapon, resolve_attack
from rules.core import SessionState


def test_hit_and_miss() -> None:
    session = SessionState(seed=1)
    weapon = Weapon(name="Stick", damage="1d1")
    attacker = CombatantState(
        name="Attacker",
        dex=0,
        armor_rating=10,
        ap=0,
        hp=10,
        weapon=weapon,
    )
    defender = CombatantState(
        name="Defender",
        dex=0,
        armor_rating=5,
        ap=0,
        hp=10,
    )

    result, _, updated = resolve_attack(
        session,
        attacker,
        defender,
        attack_roll_override=10,
    )
    assert result.hit is True
    assert updated.hp == 9

    result, _, updated = resolve_attack(
        session,
        attacker,
        defender,
        attack_roll_override=1,
        reaction="dodge",
        reaction_bonus=10,
    )
    assert result.hit is False
    assert updated.hp == 10


def test_ap_absorption_and_block() -> None:
    session = SessionState(seed=1)
    weapon = Weapon(name="Club", damage="1d1")
    attacker = CombatantState(
        name="Attacker",
        dex=0,
        armor_rating=10,
        ap=0,
        hp=10,
        weapon=weapon,
        damage_bonus=2,
    )
    defender = CombatantState(
        name="Defender",
        dex=0,
        armor_rating=5,
        ap=1,
        hp=10,
    )

    result, _, updated = resolve_attack(
        session,
        attacker,
        defender,
        attack_roll_override=10,
        reaction="block",
        reaction_ap=2,
    )
    assert result.hit is True
    assert result.ap_before == 3
    assert updated.ap == 0
    assert updated.hp == 10


def test_ap_then_hp_damage() -> None:
    session = SessionState(seed=1)
    weapon = Weapon(name="Club", damage="1d1")
    attacker = CombatantState(
        name="Attacker",
        dex=0,
        armor_rating=10,
        ap=0,
        hp=10,
        weapon=weapon,
        damage_bonus=4,
    )
    defender = CombatantState(
        name="Defender",
        dex=0,
        armor_rating=5,
        ap=2,
        hp=10,
    )

    result, _, updated = resolve_attack(
        session,
        attacker,
        defender,
        attack_roll_override=15,
    )
    assert result.hit is True
    assert updated.ap == 0
    assert updated.hp == 7


def test_crit_doubles_dice_total() -> None:
    session = SessionState(seed=2)
    weapon = Weapon(name="Dagger", damage="1d1")
    attacker = CombatantState(
        name="Attacker",
        dex=0,
        armor_rating=10,
        ap=0,
        hp=10,
        weapon=weapon,
    )
    defender = CombatantState(
        name="Defender",
        dex=0,
        armor_rating=5,
        ap=0,
        hp=10,
    )

    result, _, updated = resolve_attack(
        session,
        attacker,
        defender,
        attack_roll_override=20,
    )
    assert result.crit is True
    assert result.damage == 2
    assert updated.hp == 8


def test_counter_reaction_triggers_basic_strike() -> None:
    session = SessionState(seed=3)
    attacker = CombatantState(
        name="Attacker",
        dex=0,
        armor_rating=0,
        ap=0,
        hp=5,
        weapon=Weapon(name="Stick", damage="1d1"),
    )
    defender = CombatantState(
        name="Defender",
        dex=0,
        armor_rating=50,
        ap=0,
        hp=10,
        weapon=Weapon(name="Fist", damage="1d1"),
    )

    result, updated_attacker, _ = resolve_attack(
        session,
        attacker,
        defender,
        reaction="counter",
        attack_roll_override=1,
    )
    assert result.hit is False
    assert result.counter is not None
    assert result.counter.triggered is True
    assert updated_attacker.hp == 4
