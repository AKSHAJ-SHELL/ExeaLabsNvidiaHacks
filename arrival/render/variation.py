"""variation: post-render appearance variation over a finished sim dataset. Works on a COPY, never the source.

Backends: 'cosmos' (HTTP client to COSMOS_URL, never called from tests) and 'local_stub' (seeded colour jitter
plus mild blur, geometry fixed). A restyled frame is kept only if edge structure (and an optional robot/object
mask) survive; otherwise the original frame stays. The dataset label is 'cosmos' only after a real Cosmos success.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

SIDECAR = "arrival_variation.jsonl"
SUMMARY = "arrival_variation_summary.json"
VIDEO_DIR = "variation_videos"
FRACTION = 0.10
EDGE_CORR_MIN = 0.6
MASK_CHANGE_MAX = 0.35
BREAKER = 3  # consecutive failed cosmos requests before the rest are skipped


def _u64(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def select_frames(episode_index: int, n_frames: int, seed: int, fraction: float = FRACTION) -> list[int]:
    """The round(fraction * n) frames with the smallest hash of (episode_index, frame_index, seed), sorted."""
    if type(n_frames) is not int or n_frames < 0:
        raise ValueError("n_frames must be a non-negative integer")
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError("fraction must be finite and between 0 and 1")
    k = min(n_frames, int(round(fraction * n_frames)))
    ranked = sorted(range(n_frames), key=lambda i: (_u64(episode_index, i, seed), i))
    return sorted(ranked[:k])


def _gray(img: np.ndarray) -> np.ndarray:
    return img.astype(np.float64) @ np.array([0.299, 0.587, 0.114])


def edge_map(img: np.ndarray) -> np.ndarray:
    g = np.pad(_gray(img), 1, mode="edge")
    gx = g[1:-1, 2:] - g[1:-1, :-2]
    gy = g[2:, 1:-1] - g[:-2, 1:-1]
    return np.hypot(gx, gy)


def edge_correlation(a: np.ndarray, b: np.ndarray) -> float:
    ea, eb = edge_map(a).ravel(), edge_map(b).ravel()
    if ea.std() < 1e-9 or eb.std() < 1e-9:
        return 1.0 if ea.std() < 1e-9 and eb.std() < 1e-9 else 0.0
    return float(np.corrcoef(ea, eb)[0, 1])


def masked_change(a: np.ndarray, b: np.ndarray, mask: np.ndarray | None) -> float | None:
    """Mean abs difference inside the mask of the grey values normalised to zero mean, unit std there, so a pure
    brightness or contrast change reads as ~0 and a moved or repainted object reads high. None without a mask."""
    if mask is None or not mask.any():
        return None
    ga, gb = _gray(a)[mask], _gray(b)[mask]
    na = (ga - ga.mean()) / (ga.std() + 1e-6)
    nb = (gb - gb.mean()) / (gb.std() + 1e-6)
    return float(np.abs(na - nb).mean() / 2)


def check_frame(orig: np.ndarray, var: np.ndarray, mask: np.ndarray | None = None,
                edge_min: float = EDGE_CORR_MIN, mask_max: float = MASK_CHANGE_MAX) -> dict:
    if var.shape != orig.shape:
        return {"ok": False, "reason": f"shape {list(var.shape)} != {list(orig.shape)}",
                "edge_corr": None, "mask_change": None}
    if var.dtype != np.uint8:
        return {"ok": False, "reason": f"expected uint8 RGB frame, got {var.dtype}",
                "edge_corr": None, "mask_change": None}
    if mask is not None and (not isinstance(mask, np.ndarray) or mask.dtype != np.bool_
                             or mask.shape != orig.shape[:2]):
        return {"ok": False, "reason": "mask must be a boolean array matching frame height and width",
                "edge_corr": None, "mask_change": None}
    if np.array_equal(orig, var):
        return {"ok": False, "reason": "backend returned the original frame unchanged",
                "edge_corr": 1.0, "mask_change": 0.0 if mask is not None and mask.any() else None}
    corr = edge_correlation(orig, var)
    mc = masked_change(orig, var, mask)
    reason = None
    if not math.isfinite(corr) or (mc is not None and not math.isfinite(mc)):
        reason = "non-finite geometry check"
    elif corr < edge_min:
        reason = f"edge correlation {corr:.3f} < {edge_min}"
    elif mc is not None and mc > mask_max:
        reason = f"masked region changed {mc:.3f} > {mask_max}"
    return {"ok": reason is None, "reason": reason, "edge_corr": round(corr, 4),
            "mask_change": None if mc is None else round(mc, 4)}


def _blur3(img: np.ndarray) -> np.ndarray:
    p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    return sum(p[dy:dy + img.shape[0], dx:dx + img.shape[1]] for dy in range(3) for dx in range(3)) / 9.0


def _hue_matrix(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    k = 1 / 3
    r = math.sqrt(k)
    return np.array([
        [c + (1 - c) * k, k * (1 - c) - r * s, k * (1 - c) + r * s],
        [k * (1 - c) + r * s, c + k * (1 - c), k * (1 - c) - r * s],
        [k * (1 - c) - r * s, k * (1 - c) + r * s, c + k * (1 - c)]])


class LocalStub:
    """Seeded colour/brightness/contrast/hue jitter plus a mild blur. Not Cosmos: geometry is never moved."""

    name = "local_stub"
    model = "local_stub"
    version = "1"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def params(self, episode_index: int, frame_index: int) -> dict:
        rng = np.random.default_rng(_u64("stub", episode_index, frame_index, self.seed))
        return {"brightness": round(float(rng.uniform(0.8, 1.2)), 4), "contrast": round(float(rng.uniform(0.8, 1.25)), 4),
                "hue_deg": round(float(rng.uniform(-15, 15)), 3),
                "color_shift": [round(float(v), 2) for v in rng.uniform(-10, 10, 3)], "blur_mix": 0.4}

    def __call__(self, frame: np.ndarray, episode_index: int, frame_index: int) -> tuple[np.ndarray, dict]:
        p = self.params(episode_index, frame_index)
        x = frame.astype(np.float64) @ _hue_matrix(p["hue_deg"]).T
        x = (x - 128) * p["contrast"] + 128
        x = x * p["brightness"] + np.array(p["color_shift"])
        x = (1 - p["blur_mix"]) * x + p["blur_mix"] * _blur3(x)
        return np.clip(np.rint(x), 0, 255).astype(np.uint8), p


class CosmosClient:
    """POST the frame as PNG to url, expect an image back. Errors raise after `retries` extra attempts.
    Needs COSMOS_URL; the model and version come from the X-Cosmos-Model / X-Cosmos-Version response headers."""

    name = "cosmos"

    def __init__(self, url: str | None = None, timeout: float = 30.0, retries: int = 2, backoff: float = 0.5,
                 prompt: str = "same scene, different lighting and surface appearance"):
        from arrival import config as settings

        self.url = url if url is not None else settings.get("COSMOS_URL")
        self.timeout, self.retries, self.backoff, self.prompt = timeout, retries, backoff, prompt
        self.model, self.version = "unknown", "unknown"

    def __call__(self, frame: np.ndarray, episode_index: int, frame_index: int) -> tuple[np.ndarray, dict]:
        import imageio.v2 as imageio

        buf = io.BytesIO()
        imageio.imwrite(buf, frame, format="PNG")
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(self.backoff * attempt)
            req = urllib.request.Request(self.url, data=buf.getvalue(), method="POST", headers={
                "Content-Type": "image/png", "X-Prompt": self.prompt})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read()
                    self.model = r.headers.get("X-Cosmos-Model", self.model)
                    self.version = r.headers.get("X-Cosmos-Version", self.version)
                img = np.asarray(imageio.imread(io.BytesIO(body), format="PNG"))
                if (img.dtype != np.uint8 or img.ndim != 3 or img.shape[2] not in (3, 4)
                        or img.shape[:2] != frame.shape[:2]):
                    raise ValueError(f"expected uint8 RGB or RGBA PNG at {frame.shape[:2]}, got "
                                     f"{img.dtype} {img.shape}")
                img = img[..., :3]
                return img, {"prompt": self.prompt, "attempts": attempt + 1}
            except (urllib.error.URLError, OSError, ValueError) as e:
                last = e
        raise RuntimeError(f"cosmos request failed after {self.retries + 1} attempts: {last}")


def _read_video(path: Path) -> list[np.ndarray]:
    import imageio.v2 as imageio

    with imageio.get_reader(str(path)) as r:
        return [np.asarray(f) for f in r]


def vary_dataset(src: str | Path, dst: str | Path, backend: str = "local_stub", seed: int = 0,
                 fraction: float = FRACTION, mask: np.ndarray | None = None, client=None, fps: int | None = None,
                 edge_min: float = EDGE_CORR_MIN, mask_max: float = MASK_CHANGE_MAX) -> dict:
    """Copy src to dst, restyle the selected frames of every video, write the sidecar, summary and variant mp4s."""
    from arrival.export.lerobot import write_video

    src, dst = Path(src), Path(dst)
    if backend not in ("cosmos", "local_stub"):
        raise ValueError(f"unknown backend {backend!r}")
    select_frames(0, 0, seed, fraction)  # reject invalid fractions before copying the dataset
    if dst.exists():
        raise FileExistsError(f"{dst} exists; the copy directory must be new")
    shutil.copytree(src, dst)
    info = json.loads((dst / "meta" / "info.json").read_text())
    fps = fps or int(info.get("fps", 20))
    cli = client if client is not None else (CosmosClient() if backend == "cosmos" else LocalStub(seed))
    counts = {"selected": 0, "ok": 0, "rejected": 0, "failed": 0, "skipped": 0}
    consecutive = 0
    cosmos_ok = 0
    rows: list[dict] = []
    for vid in sorted((src / "videos").glob("chunk-*/*/episode_*.mp4")):
        key, ep = vid.parent.name, int(vid.stem.split("_")[1])
        frames = _read_video(vid)
        changed = False
        for fi in select_frames(ep, len(frames), seed, fraction):
            counts["selected"] += 1
            orig = frames[fi]
            row = {"original_id": f"{key}/ep{ep:06d}/f{fi:06d}", "variant_id": f"{key}/ep{ep:06d}/f{fi:06d}_v",
                   "episode_index": ep, "frame_index": fi, "backend": cli.name, "model": cli.model,
                   "version": cli.version, "parameters": {"seed": seed, "fraction": fraction},
                   "latency_ms": None, "status": "failed", "skipped": False, "reason": None,
                   "edge_corr": None, "mask_change": None}
            if cli.name == "cosmos" and (not cli.url or consecutive >= BREAKER):
                row.update(skipped=True, reason="COSMOS_URL not set" if not cli.url else
                           f"skipped after {BREAKER} consecutive failures")
                counts["skipped"] += 1
                counts["failed"] += 1
                rows.append(row)
                continue
            t0 = time.perf_counter()
            try:
                out, params = cli(orig, ep, fi)
            except Exception as e:  # noqa: BLE001 - any backend error leaves the frame original
                row.update(latency_ms=round((time.perf_counter() - t0) * 1000, 2), reason=str(e))
                counts["failed"] += 1
                consecutive += 1
                rows.append(row)
                continue
            consecutive = 0
            row.update(latency_ms=round((time.perf_counter() - t0) * 1000, 2), model=cli.model, version=cli.version,
                       parameters={**row["parameters"], **params})
            chk = check_frame(orig, out, mask, edge_min, mask_max)
            row.update(edge_corr=chk["edge_corr"], mask_change=chk["mask_change"], reason=chk["reason"])
            if chk["ok"]:
                row["status"] = "ok"
                counts["ok"] += 1
                cosmos_ok += cli.name == "cosmos"
                frames[fi] = out
                changed = True
            else:
                row["status"] = "rejected"
                counts["rejected"] += 1
            rows.append(row)
        if changed:
            write_video(dst / VIDEO_DIR / key / vid.name, np.stack(frames), fps)
    label = "cosmos" if cosmos_ok else ("local_stub" if backend == "local_stub" and counts["ok"] else "none")
    (dst / "meta" / SIDECAR).write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary = {"arrival_appearance_variation": label, "backend_requested": backend, "seed": seed,
               "fraction": fraction, "requests": counts.pop("selected"), **counts,
               "cosmos_model": cli.model if cli.name == "cosmos" and cosmos_ok else None,
               "added_latency_s": None, "cost_usd": None,
               "note": "frames not ok stay original; added latency and cost are unmeasured end to end"}
    (dst / "meta" / SUMMARY).write_text(json.dumps(summary, indent=2))
    info["arrival_appearance_variation"] = label
    (dst / "meta" / "info.json").write_text(json.dumps(info, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="appearance variation over a COPY of a sim dataset")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--backend", choices=["cosmos", "local_stub"], default="local_stub")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fraction", type=float, default=FRACTION)
    a = ap.parse_args(argv)
    print(json.dumps(vary_dataset(a.src, a.dst, a.backend, a.seed, a.fraction), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
