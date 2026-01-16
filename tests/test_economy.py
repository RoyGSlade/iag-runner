from types import SimpleNamespace

import pytest

from rules.economy import EconomyError, is_item_legal_for_era, quote_item_price, validate_credit_spend


def test_buying_succeeds_with_enough_credits() -> None:
    base = SimpleNamespace(stats_json={"value": 10})
    variation = SimpleNamespace(modifier_json={"price_delta": 5})
    quote = quote_item_price(base, variation)
    assert quote.total_price == 15

    gear_pack = {"credits": 20}
    updated = validate_credit_spend(gear_pack, quote.total_price)
    assert updated["credits"] == 5


def test_buying_fails_with_insufficient_credits() -> None:
    gear_pack = {"credits": 5}
    with pytest.raises(EconomyError):
        validate_credit_spend(gear_pack, 10)


def test_era_locked_item() -> None:
    allowed = is_item_legal_for_era("Space", "Plasma Pistol", ["plasma"])
    blocked = is_item_legal_for_era("Medieval", "Plasma Pistol", ["plasma"])
    assert allowed is True
    assert blocked is False


def test_era_patch_allows_plasma() -> None:
    allowed = is_item_legal_for_era(
        "Medieval",
        "Plasma Pistol",
        ["plasma"],
        era_patch={"allow_plasma": True},
    )
    assert allowed is True
