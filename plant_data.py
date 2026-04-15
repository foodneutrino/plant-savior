"""Default watering intervals for common houseplants.

Intervals are approximate days between waterings, assuming typical indoor
conditions (indirect light, room temperature, moderate humidity).
"""

# Values are watering interval in days
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


def suggest_interval(plant_type: str) -> int | None:
    """Look up a default watering interval by plant name.

    Performs case-insensitive matching. Returns None if not found.
    """
    normalized = plant_type.strip().lower()

    # Exact match
    if normalized in PLANT_INTERVALS:
        return PLANT_INTERVALS[normalized]

    # Substring match (e.g. "snake" matches "snake plant")
    for name, days in PLANT_INTERVALS.items():
        if normalized in name or name in normalized:
            return days

    return None
