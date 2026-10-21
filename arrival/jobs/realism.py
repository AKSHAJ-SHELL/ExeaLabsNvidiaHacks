"""Optional, job-local comparison of uploaded held-out frames and the compiled room."""

from __future__ import annotations

import contextlib
import json
import traceback
from pathlib import Path

import numpy as np

from arrival.eval.realism_cli import run_realism
from arrival.scan import rgbd

METRICS = ("depth_l1_m", "rgb_mae", "rgb_one_minus_ssim", "n_depth", "n_rgb", "frames")


def measure(job_dir: Path, bundle: dict, twin: dict, log=print) -> dict:
    status = {"state": "not_measured", "metrics": None, "consumed": False, "preview": False,
              "reason": "No RGB-D frames uploaded."}
    frames_dir = job_dir / "frames"
    if not frames_dir.is_dir():
        return status
    output = job_dir / "realism"
    try:
        output.mkdir(exist_ok=True)
        manifest = rgbd.load_manifest(frames_dir)
        source_id = bundle.get("source_room_id")
        if source_id and source_id != manifest.room_id:
            status["reason"] = "The scan and frame bundle name different rooms."
            return status
        if not any(f.split == "heldout" for f in manifest.frames):
            status["reason"] = "No held-out frames were supplied."
            return status
        if "realism" in twin.get("blocks_claims", []):
            status["reason"] = "This scan does not support a realism measurement."
            return status
        transform = np.eye(4)
        if "arkit_world_to_room" in bundle:
            transform = np.asarray(bundle["arkit_world_to_room"]) @ np.linalg.inv(manifest.arkit_world_to_room)
        alignment = {"source_room_id": source_id, "manifest_room_id": manifest.room_id,
                     "association": "matching_room_id" if source_id else "uploaded_together",
                     "manifest_room_to_twin": transform.tolist()}
        (output / "alignment.json").write_text(json.dumps(alignment, indent=2), encoding="utf-8")
        twin_path = output / "twin.json"
        twin_path.write_text(json.dumps(twin, indent=2), encoding="utf-8")
        report = run_realism(job_dir, out_dir=output, twin_path=twin_path, camera_transform=transform, log=log)
        status.update(consumed=True, state="measured" if report["valid"] else "invalid",
                      reason=None if report["valid"] else "The camera-offset control did not increase depth error.",
                      preview=bool(report["png"]), frame_count=len(report["frames"]["scored"]),
                      association=alignment["association"])
        if report["valid"]:
            status["metrics"] = {key: report["realism"][key] for key in METRICS}
        if report["png"]:
            # The web route serves only this fixed artifact, never a client-supplied path.
            (output / "comparison.png").write_bytes(Path(report["png"]).read_bytes())
    except Exception:
        status.update(state="error", metrics=None, preview=False, reason="Frame comparison failed.")
        with contextlib.suppress(OSError):
            (output / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        log(f"[work] {job_dir.name}: optional realism measurement failed")
    return status
