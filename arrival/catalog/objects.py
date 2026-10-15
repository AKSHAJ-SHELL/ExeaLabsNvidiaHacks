"""Object label -> catalog id."""

OBJECT_MAP = {label: label for label in ("mug", "bowl", "plate", "sponge", "apple", "bottle", "pan")}


def catalog_id(label: str) -> str:
    return OBJECT_MAP.get(label, "box")
