from pathlib import Path

from PIL import Image

from arrival.scan.four_photo import bundle_from_photos


def test_rerun_with_existing_photo_inputs(tmp_path):
    scans = tmp_path / "scans"
    source = Path(__file__).resolve().parents[1] / "scans" / "hero_kitchen" / "scan.json"
    template = scans / "hero_kitchen"
    template.mkdir(parents=True)
    (template / "scan.json").write_bytes(source.read_bytes())
    photos = []
    for i in range(4):
        path = tmp_path / f"input_{i}.png"
        Image.new("RGB", (2, 2), (i * 50, 0, 0)).save(path)
        photos.append(path)
    bundle_from_photos(photos, "room", scans_dir=scans)
    existing = sorted((scans / "room" / "photos").glob("photo_*"))
    expected = [p.read_bytes() for p in existing]
    bundle_from_photos(existing, "room", scans_dir=scans)
    assert [p.read_bytes() for p in existing] == expected
