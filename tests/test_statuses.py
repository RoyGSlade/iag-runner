from rules.statuses import (
    apply_status,
    ramp_status,
    tick_statuses,
    total_dex_penalty,
)


def test_bleeding_ramps_on_move_and_ticks_damage() -> None:
    statuses = apply_status({}, "Bleeding", stacks=1, level=1, duration=2)
    statuses = ramp_status(statuses, "Bleeding", trigger="move")
    updated, hp_delta, _ = tick_statuses(statuses, tick_type="turn")

    assert updated["Bleeding"]["stacks"] == 2
    assert updated["Bleeding"]["level"] >= 2
    assert hp_delta < 0


def test_ignited_tick_damage_scales_with_level() -> None:
    statuses = apply_status({}, "Ignited", level=2, duration=2)
    _, hp_delta, _ = tick_statuses(statuses, tick_type="turn")
    assert hp_delta == -4


def test_cold_reduces_dex() -> None:
    statuses = apply_status({}, "Cold", level=3, duration=2)
    assert total_dex_penalty(statuses) == 3


def test_disease_escalates_over_days() -> None:
    statuses = apply_status({}, "Disease", level=1)
    updated, hp_delta, _ = tick_statuses(statuses, tick_type="day")
    assert updated["Disease"]["level"] == 2
    assert hp_delta == -2


def test_asphyxiation_tick_damage() -> None:
    statuses = apply_status({}, "Asphyxiation", level=2, duration=2)
    _, hp_delta, _ = tick_statuses(statuses, tick_type="turn")
    assert hp_delta == -4
