"""Default watering intervals for common houseplants.

Intervals are approximate days between waterings, assuming typical
indoor conditions (indirect light, room temperature, moderate humidity).
"""

from dataclasses import dataclass

PLANT_INTERVALS: dict[str, int] = {
    "aloe vera": 14,
    "basil": 3,
    "bird of paradise": 7,
    "boston fern": 5,
    "cactus": 21,
    "calathea": 5,
    "chinese evergreen": 7,
    "croton": 5,
    "dracaena": 10,
    "english ivy": 5,
    "fiddle leaf fig": 7,
    "golden pothos": 7,
    "jade plant": 14,
    "lavender": 10,
    "mint": 3,
    "monstera": 7,
    "orchid": 7,
    "parlor palm": 7,
    "peace lily": 5,
    "philodendron": 7,
    "pothos": 7,
    "prayer plant": 5,
    "rosemary": 7,
    "rubber plant": 10,
    "snake plant": 14,
    "spider plant": 7,
    "string of pearls": 10,
    "succulent": 14,
    "swiss cheese plant": 7,
    "zz plant": 14,
}


@dataclass(frozen=True)
class IntervalMatch:
    """Result of a plant-name lookup against :data:`PLANT_INTERVALS`.

    Attributes:
        interval: Suggested watering interval in days.
        match: Title-cased display name of the matched entry (e.g.
            ``"Snake Plant"`` when the caller typed ``"snake"``).
    """

    interval: int
    match: str


def suggest_interval(plant_type: str) -> IntervalMatch | None:
    """Look up a default watering interval by plant name.

    Matching is case-insensitive and falls back to substring matching,
    so ``"snake"`` finds ``"snake plant"``. Returns ``None`` when no
    entry resembles the input.

    Args:
        plant_type: User-provided species or common name.

    Returns:
        An :class:`IntervalMatch` on success, or ``None`` if no entry
        matched.
    """
    normalized = plant_type.strip().lower()
    if not normalized:
        return None

    if normalized in PLANT_INTERVALS:
        return IntervalMatch(PLANT_INTERVALS[normalized], normalized.title())

    for name, days in PLANT_INTERVALS.items():
        if normalized in name or name in normalized:
            return IntervalMatch(days, name.title())

    return None
