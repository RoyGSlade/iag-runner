from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable


class EconomyError(ValueError):
    pass


@dataclass(frozen=True)
class PriceQuote:
    base_price: int
    modifier: int
    total_price: int


def quote_item_price(base: Any, variation: Any | None = None) -> PriceQuote:
    base_price = _extract_price(getattr(base, "stats_json", None))
    modifier = _extract_price_modifier(getattr(variation, "modifier_json", None))
    total_price = max(0, base_price + modifier)
    multiplier = _extract_price_multiplier(getattr(variation, "modifier_json", None))
    if multiplier is not None:
        total_price = max(0, int(round(total_price * multiplier)))
    return PriceQuote(base_price=base_price, modifier=modifier, total_price=total_price)


def validate_credit_spend(gear_pack: dict | None, cost: int) -> dict:
    if cost < 0:
        raise EconomyError("Cost must be non-negative.")
    updated = copy.deepcopy(gear_pack or {})
    credits = int(updated.get("credits") or updated.get("starting_credits") or 0)
    if credits < cost:
        raise EconomyError("Insufficient credits.")
    updated["credits"] = credits - cost
    return updated


def add_item_to_gear(gear_pack: dict | None, item_entry: dict) -> dict:
    updated = copy.deepcopy(gear_pack or {})
    items = updated.get("items")
    if not isinstance(items, list):
        items = []
    items.append(item_entry)
    updated["items"] = items
    return updated


def is_item_legal_for_era(
    era_name: str | None,
    item_name: str,
    tags: Iterable[str] | None,
    era_profile: dict | None = None,
    era_patch: dict | None = None,
) -> bool:
    era = (era_name or "").strip().lower()
    tag_set = {tag.strip().lower() for tag in (tags or []) if isinstance(tag, str)}
    name_lower = item_name.strip().lower()

    illegal_tags = set()
    illegal_tags.update(_extract_tag_list(era_profile, "illegal_tags", "restricted_tags"))
    illegal_tags.update(_extract_tag_list(era_patch, "illegal_tags", "restricted_tags"))

    illegal_items = set()
    illegal_items.update(_extract_tag_list(era_profile, "illegal_items"))
    illegal_items.update(_extract_tag_list(era_patch, "illegal_items"))

    if name_lower in illegal_items:
        return False
    if illegal_tags.intersection(tag_set):
        return False

    allow_plasma = _extract_bool(
        era_patch, "allow_plasma", "allow_energy_weapons", "allow_advanced_weapons"
    ) or _extract_bool(
        era_profile, "allow_plasma", "allow_energy_weapons", "allow_advanced_weapons"
    )

    if era != "space" and not allow_plasma:
        if "plasma" in tag_set or "energy" in tag_set or "laser" in tag_set:
            return False
        if "plasma" in name_lower or "laser" in name_lower:
            return False

    return True


def _extract_price(stats: Any) -> int:
    if not isinstance(stats, dict):
        return 0
    for key in ("value", "price", "cost", "credits"):
        value = stats.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _extract_price_modifier(stats: Any) -> int:
    if not isinstance(stats, dict):
        return 0
    for key in ("price_delta", "value_delta", "price_add", "value_add"):
        value = stats.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _extract_price_multiplier(stats: Any) -> float | None:
    if not isinstance(stats, dict):
        return None
    for key in ("price_multiplier", "value_multiplier", "multiplier"):
        value = stats.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _extract_tag_list(data: dict | None, *keys: str) -> set[str]:
    if not isinstance(data, dict):
        return set()
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return {str(item).strip().lower() for item in value}
        if isinstance(value, str):
            return {value.strip().lower()}
    return set()


def _extract_bool(data: dict | None, *keys: str) -> bool:
    if not isinstance(data, dict):
        return False
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            return value
    return False


def _merge_tags(base: dict | None, modifier: dict | None) -> list[str]:
    tags: list[str] = []
    for source in (base, modifier):
        if isinstance(source, dict):
            value = source.get("tags")
            if isinstance(value, list):
                tags.extend([str(item) for item in value])
    return tags


def item_tags(base: Any, variation: Any | None = None) -> list[str]:
    base_stats = getattr(base, "stats_json", None)
    variation_stats = getattr(variation, "modifier_json", None)
    return _merge_tags(base_stats, variation_stats)
