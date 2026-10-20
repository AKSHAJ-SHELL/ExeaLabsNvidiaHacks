# DAT-2a: offline loader conformance check

Issues: #37 (DAT-1, third box), #63 (DAT-2, offline part).

```bash
python -m arrival sim --episodes 2 --people 0 --res 64 --out /tmp/ds
python scripts/check_dataset_loader.py /tmp/ds/datasets/hero_kitchen_sim          # short report, exit 0 or 1
python scripts/check_dataset_loader.py /tmp/ds/datasets/hero_kitchen_sim --json   # full result incl. recomputed stats
```

Each finding has a `code`. Failures: `placeholder`, `missing_meta`, `fps_invalid`, `modality_slices`, `video_key`,
`annotation_key`, `missing_parquet`, `parquet_unreadable`, `schema`, `episode_length`, `task_index_unresolved`,
`timestamp_fps`, `short_episode`, `nonfinite`, `stats_missing`, `stats_mismatch`, `stats_std_zero`, `missing_video`,
`video_decode`, `video_frames`, `video_fps`, `video_shape`. Warnings: `constant_dim`, `stats_no_quantiles`.

What it reproduces from the loader, and what it does not:

- Reads only the dataset's own files; the 16-step horizon is `HORIZON` in `loader_check.py`, copied from
  `configs/gr00t/arrival_panda_config.py` (that file imports `gr00t`, so it is not imported here).
- The arm action is relative: `action[t+k] - state[t]` for k in 0..15, tail padded with the last action.
- A window starting in the last 15 frames of an episode is counted as padded.
- Parquet is read per episode. Only the first, middle and last episode's mp4 are decoded per camera; every episode's
  mp4 is checked for existence.
- Not covered: the real `gr00t` dataset class, its transforms, or GPU-side batching. DAT-1 stays open until a real load.
