"""RoomPlan / scan category -> RoboCasa fixture type."""

FIXTURE_MAP = {
    "counter": "counter",
    "sink": "sink",
    "refrigerator": "fridge_bottom_freezer",
    "stove": "stove",
    "oven": "stove",
    "dishwasher": "dishwasher",
    "storage": "hinge_cabinet",
    "table": "counter",
}


def fixture_type(category: str) -> str:
    return FIXTURE_MAP.get(category, "box")


def default_config_name(category: str) -> str | None:
    return "dining" if category == "table" else None
