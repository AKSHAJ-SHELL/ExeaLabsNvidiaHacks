"""RoomPlan / scan category -> RoboCasa fixture type, plus a default size per category."""

# Every case of Apple's CapturedRoom.Object.Category (iOS 16 to 17), snake-cased, plus our own `counter`.
# RoboCasa has no bed, sofa or bathtub; those stay a plain `box` so the scan is not silently dropped.
FIXTURE_MAP = {
    "counter": "counter",
    "sink": "sink",
    "refrigerator": "fridge_bottom_freezer",
    "stove": "stove",
    "oven": "stove",
    "dishwasher": "dishwasher",
    "storage": "hinge_cabinet",
    "table": "counter",
    "washer_dryer": "box",
    "chair": "box",
    "sofa": "box",
    "bed": "box",
    "bathtub": "box",
    "toilet": "box",
    "television": "box",
    "fireplace": "box",
    "stairs": "box",
}

# Full extents [x, y, z] in metres, Z-up, used when a scan object has no usable dimensions.
DEFAULT_SIZES = {
    "counter": [1.8, 0.65, 0.92],
    "sink": [0.6, 0.5, 0.25],
    "refrigerator": [0.75, 0.7, 1.8],
    "stove": [0.7, 0.65, 0.9],
    "oven": [0.6, 0.6, 0.6],
    "dishwasher": [0.6, 0.6, 0.85],
    "storage": [0.9, 0.5, 2.0],
    "table": [1.4, 0.8, 0.75],
    "washer_dryer": [0.6, 0.6, 0.85],
    "chair": [0.5, 0.5, 0.9],
    "sofa": [2.0, 0.9, 0.85],
    "bed": [1.6, 2.0, 0.5],
    "bathtub": [1.7, 0.75, 0.55],
    "toilet": [0.4, 0.7, 0.8],
    "television": [1.2, 0.1, 0.7],
    "fireplace": [1.2, 0.4, 1.0],
    "stairs": [1.0, 3.0, 2.7],
}
FALLBACK_SIZE = [0.5, 0.5, 0.5]


def fixture_type(category: str) -> str:
    return FIXTURE_MAP.get(category, "box")


def default_config_name(category: str) -> str | None:
    return "dining" if category == "table" else None


def default_size(category: str) -> list[float]:
    return list(DEFAULT_SIZES.get(category, FALLBACK_SIZE))
