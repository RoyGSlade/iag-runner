import pytest

from rules.validation import ValidationError, validate_weapon_allowed


def test_prehistoric_blocks_guns() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_weapon_allowed("Prehistoric", ["gun"])
    assert "Prehistoric" in str(excinfo.value)


def test_medieval_blocks_guns_without_patch() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_weapon_allowed("Medieval", ["gun"])
    assert "Medieval" in str(excinfo.value)


def test_medieval_allows_guns_with_patch() -> None:
    validate_weapon_allowed("Medieval", ["gun"], {"allow_guns": True})


def test_non_gun_is_allowed() -> None:
    validate_weapon_allowed("Prehistoric", ["melee"])
