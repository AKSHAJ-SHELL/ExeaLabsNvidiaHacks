from pathlib import Path

import imageio.v2 as imageio

from arrival.export.quality import _blank_video


class EmptyReader:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def __iter__(self):
        return iter(())


def test_empty_video_is_flagged(monkeypatch):
    monkeypatch.setattr(imageio, "get_reader", lambda *_: EmptyReader())
    assert _blank_video(Path("camera.mp4")) == "camera.mp4: video has no frames"
