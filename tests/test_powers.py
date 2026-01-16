from types import SimpleNamespace

import pytest

from rules.powers import PowerError, use_power


def test_powers_locked_outside_space_era() -> None:
    character = SimpleNamespace(
        attributes_json={"powers": ["sherlock.scanning_gaze"]},
        statuses_json={},
    )
    with pytest.raises(PowerError) as excinfo:
        use_power("Medieval", character, "sherlock.scanning_gaze")
    assert "Space" in str(excinfo.value)


def test_sherlock_effect_applies_concentration() -> None:
    character = SimpleNamespace(
        attributes_json={"powers": ["sherlock.scanning_gaze"]},
        statuses_json={},
    )
    result = use_power("Space", character, "sherlock.scanning_gaze")
    assert result.updated_statuses["Concentration"]["duration"] == 1


def test_teleportation_effect_applies_hidden() -> None:
    character = SimpleNamespace(
        attributes_json={"powers": ["teleportation.vanish"]},
        statuses_json={},
    )
    result = use_power("Space", character, "teleportation.vanish")
    assert "Hidden" in result.updated_statuses


def test_power_drain_effect_adds_reserve_charge() -> None:
    character = SimpleNamespace(
        attributes_json={"powers": ["power_drain.reserve"]},
        statuses_json={},
    )
    result = use_power("Space", character, "power_drain.reserve")
    assert result.updated_attributes["resources"]["reserve_charges"] == 1


def test_superspeed_effect_adds_extra_actions() -> None:
    character = SimpleNamespace(
        attributes_json={"powers": ["superspeed.time_dilation"]},
        statuses_json={},
    )
    result = use_power("Space", character, "superspeed.time_dilation")
    assert result.updated_attributes["resources"]["extra_actions"] == 2
