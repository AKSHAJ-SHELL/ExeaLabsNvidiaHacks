from pathlib import Path

import pytest

from arrival.scan.four_photo import bundle_from_photos


def test_invalid_photo_is_rejected_before_room_is_written(tmp_path):
    scans = tmp_path / "scans"
    template = scans / "hero_kitchen"
    template.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "scans" / "hero_kitchen" / "scan.json"
    (template / "scan.json").write_bytes(source.read_bytes())
    photos = []
    for i in range(4):
        photo = tmp_path / f"photo_{i}.png"
        photo.write_bytes(b"not an image")
        photos.append(photo)
    with pytest.raises(ValueError, match="not a readable image"):
        bundle_from_photos(photos, "room", scans_dir=scans)
    assert not (scans / "room").exists()
