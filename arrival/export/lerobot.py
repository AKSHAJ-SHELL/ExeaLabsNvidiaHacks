"""GR00T LeRobot v2 writer: parquet per episode, mp4 per selected episode, meta/*."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from arrival.render import sim_texture

VIDEO_KEY = "observation.images.ego_view"
SPARSE_EVERY = 125

MODALITY = {
    "state": {"single_arm": {"start": 0, "end": 7}, "gripper": {"start": 7, "end": 8}},
    "action": {
        "single_arm": {"start": 0, "end": 7, "absolute": True},
        "gripper": {"start": 7, "end": 8, "absolute": True},
    },
    "video": {"ego_view": {"original_key": VIDEO_KEY}},
    "annotation": {"human.task_description": {}},
}

SCHEMA = pa.schema([
    ("observation.state", pa.list_(pa.float32())),
    ("action", pa.list_(pa.float32())),
    ("timestamp", pa.float32()),
    ("annotation.human.task_description", pa.int64()),
    ("task_index", pa.int64()),
    ("episode_index", pa.int64()),
    ("index", pa.int64()),
    ("next.reward", pa.float32()),
    ("next.done", pa.bool_()),
])


def wants_video(policy: str, episode_index: int) -> bool:
    if policy == "all":
        return True
    if policy == "sparse":
        return episode_index % SPARSE_EVERY == 0
    return False


def write_video(path: Path, frames: np.ndarray, fps: int) -> None:
    import imageio.v2 as imageio

    path.parent.mkdir(parents=True, exist_ok=True)
    with imageio.get_writer(str(path), fps=fps, codec="libx264", pixelformat="yuv420p",
                            macro_block_size=16, ffmpeg_log_level="error") as w:
        for f in frames:
            w.append_data(f)


class LeRobotWriter:
    def __init__(self, root: str | Path, room_id: str, video_policy: str, fps: int = 20,
                 room_center_x: float = 2.0):
        self.root = Path(root)
        self.room_id = room_id
        self.video_policy = video_policy
        self.fps = fps
        self.room_center_x = room_center_x
        if self.root.exists():
            shutil.rmtree(self.root)
        (self.root / "meta").mkdir(parents=True)
        (self.root / "data" / "chunk-000").mkdir(parents=True)
        self.sidecar_path = self.root.parent / f"{room_id}.cartesian.jsonl"
        self._sidecar = open(self.sidecar_path, "w")
        self.task_index: dict[str, int] = {}
        self.episodes: list[dict] = []
        self.families: set[str] = set()
        self.total_frames = 0
        self.videos = 0

    def add(self, attempt: dict) -> int:
        ep = len(self.episodes)
        task = attempt["task"]
        instr = task["instruction"]
        ti = self.task_index.setdefault(instr, len(self.task_index))
        frames = attempt["frames"]
        n = len(frames)
        state = np.array([f["joint"] + [f["gripper"]] for f in frames], dtype=np.float32)
        reward = np.zeros(n, dtype=np.float32)
        if attempt["success"]:
            reward[-1] = 1.0
        done = np.zeros(n, dtype=bool)
        done[-1] = True
        state_list = pa.array(list(state), type=pa.list_(pa.float32()))
        table = pa.Table.from_arrays([
            state_list,
            state_list,  # absolute targets: action[i] == state[i]
            pa.array(np.array([f["t"] for f in frames], dtype=np.float32)),
            pa.array(np.full(n, ti, dtype=np.int64)),
            pa.array(np.full(n, ti, dtype=np.int64)),
            pa.array(np.full(n, ep, dtype=np.int64)),
            pa.array(np.arange(self.total_frames, self.total_frames + n, dtype=np.int64)),
            pa.array(reward),
            pa.array(done),
        ], schema=SCHEMA)
        pq.write_table(table, self.root / "data" / "chunk-000" / f"episode_{ep:06d}.parquet")
        if wants_video(self.video_policy, ep):
            imgs = sim_texture.render_episode(frames, task["lighting"], self.room_center_x)
            write_video(self.root / "videos" / "chunk-000" / VIDEO_KEY / f"episode_{ep:06d}.mp4", imgs, self.fps)
            self.videos += 1
        self._sidecar.write(json.dumps({"episode_index": ep, "task_id": task["task_id"], "frames": frames}) + "\n")
        self.episodes.append({"episode_index": ep, "tasks": [instr], "length": n,
                              "walkin_family": task["family"], "walkin_lighting": task["lighting"]})
        self.families.add(task["family"])
        self.total_frames += n
        return ep

    def finish(self, attempts: int) -> dict:
        self._sidecar.close()
        meta = self.root / "meta"
        with open(meta / "tasks.jsonl", "w") as f:
            for instr, ti in self.task_index.items():
                f.write(json.dumps({"task_index": ti, "task": instr}) + "\n")
        with open(meta / "episodes.jsonl", "w") as f:
            for e in self.episodes:
                f.write(json.dumps(e) + "\n")
        (meta / "modality.json").write_text(json.dumps(MODALITY, indent=2))
        (meta / "embodiment.json").write_text(json.dumps({
            "embodiment": "robocasa_panda",
            "dof_arm": 7,
            "dof_gripper": 1,
            "control": "absolute_joint_position",
            "joints_are_placeholder": True,
            "cartesian_sidecar": f"../../{self.room_id}.cartesian.jsonl",
            "note": "single_arm values are zeros until a physics generator fills them. "
                    "Do not fine-tune on this dataset while joints_are_placeholder is true.",
        }, indent=2))
        n = len(self.episodes)
        info = {
            "codebase_version": "v2.1",
            "robot_type": "robocasa_panda",
            "fps": self.fps,
            "total_episodes": n,
            "total_frames": self.total_frames,
            "total_tasks": len(self.task_index),
            "total_videos": self.videos,
            "total_chunks": 1,
            "chunks_size": 1000,
            "splits": {"train": f"0:{n}"},
            "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
            "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
            "walkin_generator": "scripted_retarget",
            "walkin_physically_valid": False,
            "walkin_successes": n,
            "walkin_attempts": attempts,
            "walkin_video_policy": self.video_policy,
            "walkin_appearance": sim_texture.APPEARANCE,
            "walkin_room_id": self.room_id,
            "walkin_families": sorted(self.families),
            "features": {
                "observation.state": {"dtype": "float32", "shape": [8]},
                "action": {"dtype": "float32", "shape": [8]},
                VIDEO_KEY: {"dtype": "video", "shape": [64, 64, 3],
                            "names": ["height", "width", "channel"],
                            "video_info": {"video.fps": self.fps, "video.codec": "h264"}},
                "timestamp": {"dtype": "float32", "shape": [1]},
                "annotation.human.task_description": {"dtype": "int64", "shape": [1]},
                "task_index": {"dtype": "int64", "shape": [1]},
                "episode_index": {"dtype": "int64", "shape": [1]},
                "index": {"dtype": "int64", "shape": [1]},
                "next.reward": {"dtype": "float32", "shape": [1]},
                "next.done": {"dtype": "bool", "shape": [1]},
            },
        }
        (meta / "info.json").write_text(json.dumps(info, indent=2))
        return info
