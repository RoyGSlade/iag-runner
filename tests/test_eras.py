from rules.eras import get_skill_for_era, is_gear_category_illegal


def test_skill_alias_patch_resolution() -> None:
    era = {
        "profile_json": {"skill_aliases": {"gunning": "Archery"}},
        "patch_json": {"skill_aliases": {"gunning": "Crossbow"}},
    }
    assert get_skill_for_era("Gunning", era) == "Crossbow"


def test_illegal_gear_category_flagged() -> None:
    era = {"profile_json": {"illegal_gear_categories": ["plasma"]}}
    assert is_gear_category_illegal("plasma", era) is True
    assert is_gear_category_illegal("melee", era) is False
