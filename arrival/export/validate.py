"""Structural checker for a GR00T LeRobot v2 folder. Does not import GR00T."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from arrival.export.lerobot import MODALITY, VIDEO_KEY

META = ("info.json", "tasks.jsonl", "episodes.jsonl", "modality.json", "embodiment.json")
COLUMNS = ("observation.state", "action", "timestamp", "annotation.human.task_description",
           "task_index", "episode_index", "index", "next.reward", "next.done")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    if not root.is_dir():
        return [f"{root} is not a directory"]
    missing = [m for m in META if not (root / "meta" / m).is_file()]
    if missing:
        return [f"missing meta/{m}" for m in missing]
    info = json.loads((root / "meta" / "info.json").read_text())
    modality = json.loads((root / "meta" / "modality.json").read_text())
    for group in ("state", "action"):
        for key in ("single_arm", "gripper"):
            want = MODALITY[group][key]
            got = modality.get(group, {}).get(key, {})
            if (got.get("start"), got.get("end")) != (want["start"], want["end"]):
                errors.append(f"modality {group}.{key} slice {got} != {want}")
    if modality.get("video", {}).get("ego_view", {}).get("original_key") != VIDEO_KEY:
        errors.append("modality video.ego_view.original_key is wrong")
    if not isinstance(info.get("walkin_physically_valid"), bool):
        errors.append("info.walkin_physically_valid must be a bool")

    episodes = _jsonl(root / "meta" / "episodes.jsonl")
    tasks = _jsonl(root / "meta" / "tasks.jsonl")
    if len(episodes) != info.get("total_episodes"):
        errors.append(f"episodes.jsonl has {len(episodes)} rows, info.total_episodes={info.get('total_episodes')}")
    if sum(e["length"] for e in episodes) != info.get("total_frames"):
        errors.append("sum of episode lengths != info.total_frames")
    if len(tasks) != info.get("total_tasks"):
        errors.append(f"tasks.jsonl has {len(tasks)} rows, info.total_tasks={info.get('total_tasks')}")

    files = sorted((root / "data" / "chunk-000").glob("episode_*.parquet"))
    if len(files) != info.get("total_episodes"):
        errors.append(f"{len(files)} parquet files, info.total_episodes={info.get('total_episodes')}")
    expected = [f"episode_{i:06d}.parquet" for i in range(len(files))]
    if [f.name for f in files] != expected:
        errors.append("parquet episode indexes are not contiguous from 0")
    for i, f in enumerate(files):
        # Full-check the first few files, schema-only check the rest (keeps 1,000 episodes fast).
        if i < 3 or i == len(files) - 1:
            t = pq.read_table(f)
            cols = set(t.column_names)
            for c in COLUMNS:
                if c not in cols:
                    errors.append(f"{f.name}: missing column {c}")
            if "observation.state" in cols and t.num_rows:
                if len(t.column("observation.state")[0].as_py()) != 8:
                    errors.append(f"{f.name}: observation.state length != 8")
                if i < len(episodes) and t.num_rows != episodes[i]["length"]:
                    errors.append(f"{f.name}: row count != episodes.jsonl length")
        else:
            names = pq.read_schema(f).names
            if "observation.state" not in names:
                errors.append(f"{f.name}: missing observation.state")

    policy = info.get("walkin_video_policy")
    mp4s = list((root / "videos" / "chunk-000" / VIDEO_KEY).glob("*.mp4"))
    n = info.get("total_episodes", 0)
    if policy == "sparse":
        need = 8 if n >= 1000 else (n + 124) // 125
        if len(mp4s) < need:
            errors.append(f"sparse policy needs at least {need} mp4s, found {len(mp4s)}")
    elif policy == "all":
        if len(mp4s) != n:
            errors.append(f"video policy 'all' needs {n} mp4s, found {len(mp4s)}")
    elif policy != "none":
        errors.append(f"unknown walkin_video_policy {policy!r}")
    return errors
