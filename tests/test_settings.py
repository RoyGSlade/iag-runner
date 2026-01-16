from rules.settings import generate_location_name


def test_generate_location_name_deterministic() -> None:
    name = generate_location_name(
        era_name="Space",
        setting_type="space station",
        seed=42,
    )
    assert name == "Nova Station"


def test_generate_location_name_varies_by_type() -> None:
    station = generate_location_name(
        era_name="Space",
        setting_type="space station",
        seed=42,
    )
    frontier = generate_location_name(
        era_name="Space",
        setting_type="frontier town",
        seed=42,
    )
    assert station != frontier
