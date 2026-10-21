# P3: timed human teleoperation, 2026-10-21

One operator completed 20 successful `counter_to_sink` demonstrations in `hero_kitchen` using the keyboard. The run includes all 26 attempts and their operator time. Practice is excluded. This completes P3's collection requirement; the generated-versus-teleoperated cloud comparison in C3 / [OPS-3](https://github.com/AvnehSBhatia/ExeaLabsNvidiaHacks/issues/67) remains unmeasured.

| Measurement | Result |
|---|---|
| Successful attempts | 20 |
| Total attempts | 26 |
| Unsuccessful attempts | 6 |
| Recorded operator time, including unsuccessful attempts | 1230.359 s (20.5 min) |
| Operator seconds per successful demo | 61.518 s |
| Assumed operator rate | USD 2/hour |
| Declared setup cost | USD 0 |
| Total cost basis at that rate | USD 0.6835 |
| Cost basis per successful demo | USD 0.0342 |
| Recorded episodes / frames / videos | 20 / 22669 / 40 |

The hourly rate and setup cost are assumptions, not invoices. The timer runs from scene readiness to judgement, including pauses, mistakes and abandoned attempts. This is one operator in one simulated room, with no people present. It does not measure real-robot performance, policy learning, or cloud savings.

## Source and files

Capture revision: [db26a01ce16dd848a900aa5cf145296ee03e4a3e](https://github.com/AvnehSBhatia/ExeaLabsNvidiaHacks/commit/db26a01ce16dd848a900aa5cf145296ee03e4a3e), from L20 / PR #113. The measured session started at `2026-10-21T04:24:59.0452202Z`. It used seed 0, no walking people, a fixed procedural arm with 8-dimensional state and action, and ego and wrist cameras at 128 x 128 pixels and 20 fps. The dataset labels are `arrival_generator: teleop_keyboard` and `arrival_physically_valid: true`.

[session.json](session.json) records the revision and capture arguments. [teleop_baseline.json](teleop_baseline.json) is accepted by `arrival.eval.cost.load_baseline`. [The attempt log](reports/hero_kitchen_teleop_attempts.jsonl) is an unchanged copy of the recorded JSONL. The portable copies replace only the machine-specific output path in the session and the attempt-log path in the baseline. The latter is relative to the baseline's directory. The original local recording is unchanged.

The recorded dataset is distributed separately as `p3-teleop-2026-10-21.zip` (5,083,316 bytes). **Publication pending:** the archive is prepared locally; a download URL must be added when it is uploaded. No dataset files or videos are added to Git.

The ZIP contains a `p3-teleop-2026-10-21/` directory with the baseline, session, attempt log, `datasets/hero_kitchen_teleop/`, and [SHA256SUMS](SHA256SUMS). Its SHA-256 is in [archive.sha256](archive.sha256). All 70 listed files matched their checksums after extraction, and the extracted dataset passed validation. The manifest paths are relative to the extracted directory.

## Validation and limits

Checks below used revision `b4f3e61521105d5e37d0075af980dc174042e54c`. Run the commands from that checkout after extracting the archive under `out/`:

```bash
python -m arrival validate out/p3-teleop-2026-10-21/datasets/hero_kitchen_teleop
python -m arrival validate out/p3-teleop-2026-10-21/datasets/hero_kitchen_teleop --episodes --frames
```

The basic validator exits 0: `20 episodes, 22669 frames, 6 tasks, 1 chunk(s), 40 videos, video_policy=all, physically_valid=True`. The baseline counts match the attempt log. Logged per-attempt times sum to 1230.357 s; the baseline stores 1230.359 s because the individual log entries are rounded to milliseconds.

The episode and frame quality check exits 1: 19 episodes pass and episode 0 is flagged `length_outlier`, at 13406 steps against a family median of 444.5 (limit 2.5x). Its attempt took 674.028 operator seconds. It succeeded by the simulation oracle and remains in the dataset and timing totals. No episodes were filtered to improve the result. There were no other flags from the available unreadable, nonfinite, zero-motion, stuck-arm, joint-limit or blank-video checks. Carried-object tilt and whether the wrist view usefully frames the object are not checked by this validator. Review the long episode before using these recordings as training seeds.

A generated comparison must use the same room, task family, success rule and output settings, with its source revision recorded. Real Nebius usage and pricing are still needed for C3. The assumed operator cost here is not a measured cloud cost.
