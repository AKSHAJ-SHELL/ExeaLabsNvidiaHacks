# Agent tasks

Do these in order. Do not start T+1 until T's done check passes. Do not add tasks. If a step blocks, use the fallback in the task and record it in `docs/BUILD-LOG.md` (create that file, one short paragraph per fallback).

## T01 — project skeleton

Create the tree in [05-repo-map.md](05-repo-map.md), `LICENSE` (Apache-2.0, copyright 2026 Exea Labs), `pyproject.toml`, empty modules, and a CLI that accepts `demo`, `validate`, and `serve` and exits 2 on an unknown command.

Done when: `python -m pip install -e ".[dev]"` works and `python -m arrival` exits 2.

## T02 — sample scan

Write `scans/hero_kitchen/scan.json` and `scans/hero_kitchen/roomplan.json` exactly to the numbers in [04-contracts.md](04-contracts.md). Implement `arrival.scan.bundle.load` and `arrival.scan.roomplan.to_bundle`.

Done when: `tests/test_roomplan.py` checks the sink center `[1.6, 0.40, 0.85]` and size `[0.6, 0.5, 0.25]`, and rejects a bundle with `frame` not `z_up`.

## T03 — four-photo slot

Implement `bundle_from_photos` per the contract. Test with four tiny PNG files created in `tmp_path`.

Done when: the returned bundle has `geometry_source == "four_photo_unmeasured"` and `blocks_claims == ["geometry", "realism"]`, and the hero fixture ids are present. Passing 3 paths raises `ValueError`.

## T04 — catalog and compiler

Implement the fixture map, object map, counter synthesis, `twin.json`, and `layout.yaml`.

Done when: `tests/test_compile.py` shows

- hero `sink_1` type is `sink` and position z is `0.85`
- hero `fridge_1` type is `fridge_bottom_freezer`
- a bundle whose only fixture is a RoomPlan `television` compiles to `type: box`
- a sink-only bundle with no counter gains a synthesized counter of height `0.92` and center z `0.46`
- `layout.yaml` parses and contains `main_group` and `bottom_row`

## T05 — tasks

Implement the proposer. Pure function of a twin dict.

Done when: `tests/test_tasks.py` shows both families, mug and bowl as source objects, sponge absent as a source, four wordings for one mug sink task, lighting values only `dim|neutral|bright`, and no task contains a people field or a cosmos field.

## T06 — generator and oracle

Implement scripted segments, retarget, and the distance oracle. Deterministic under seed 0.

Done when: a unit test builds 20 attempts, asserts exactly 2 misses (indexes 9 and 19), asserts a successful episode has length 80, gripper above 0.5 on a middle frame, and the object within 0.05 m of the target on the last frame. A miss keeps the object at the start pose.

## T07 — renderer

Implement `sim_texture` pixel rule. `arrival.render.splat.render` raises `SplatCompositeNotImplemented`.

Done when: a dim frame's pixel `(0, 0)` is `(28, 32, 38)`, and frame 0 differs from frame 40 on a successful mug episode.

## T08 — export and validate

Implement the LeRobot writer and validator.

Done when: `tests/test_dataset.py` runs `demo` logic in-process for 4 episodes (call the library, do not shell out), writes to `tmp_path`, validator exits 0, `walkin_physically_valid` is false, both families appear in `tasks.json`, modality gripper slice is `[7, 8]`, and a sparse policy is not required for this 4-episode test (`--videos all`, 4 mp4s).

## T09 — report

Write `out/reports/<room>.json` from the same run. Teleop, usefulness, and realism stay `null`. Dollar rows match the contract.

Done when:

- A 4-success run reports `successes == 4`, `attempts == 4`, `dropped == 0`. Misses start at attempt index 9, so they are outside this prefix.
- A 20-success run reports `successes == 20`, `attempts == 22`, `dropped == 2`. Those drops are attempt indexes 9 and 19.
- A 1,000-success run reports `successes == 1000`, `attempts == 1111`, `dropped == 111`. The unit test may call the counter without rendering video.

## T10 — CLI demo

Wire `python -m arrival demo`. Create `out/` directories as needed. Print the dataset path and the report path on stdout.

Done when: the 4-episode command passes `validate` in under 60 seconds.

## T11 — one thousand

Run `python -m arrival demo --episodes 1000 --videos sparse`. If it exceeds 15 minutes, stop the encode, keep parquet generation, set the default video policy for this command to sparse, and write the timing into `docs/BUILD-LOG.md`. Do not commit `out/`.

Done when: validator exits 0, `total_episodes == 1000`, at least 8 mp4 files exist, both task families are present.

## T12 — web

Implement the four routes in [02-mvp-tonight.md](02-mvp-tonight.md). HTML can be minimal: one document per page, no frontend build. Show `walkin_physically_valid` as text on the room page.

`POST /jobs` accepts `multipart/form-data` with a file field `scan`. It stores the file and writes status `queued`. It does not import the compiler.

Done when: `tests/test_web.py` uses `http.client` against a server on port 0 (pick a free port) and checks GET `/` contains `hero_kitchen`, POST returns 202 and `queued`, and a 201-MB body is not required. Check the 413 path with a limit override in the handler if generating a 201-MB body is slow: call the limit function with `content_length=201*1024*1024` and expect rejection. Also POST a small file and expect 202.

## T13 — README, license note, prior art

Rewrite root `README.md` for a reviewer. Keep one line that future work happens on a branch and a pull request.

`docs/PRIOR-ART.md` states:

- Already existed before this hackathon, in <https://github.com/AvnehSBhatia/Walk-In>: four-photo capture, Marble reconstruction, MuJoCo room, Spot and humanoid rigs, skill-level pick that attaches the object to the hand, scripted oracle, chat JSONL.
- Built in this repo for Arrival: RoomPlan normalization, RoboCasa-subset layout compiler, task variations, scripted retarget into GR00T LeRobot v2, sim-texture frames, local pre-scanned room page, queued upload.

README cost table columns: Step, Nebius product, Measured USD. Use the rows in [03-architecture.md](03-architecture.md). All measured cells say "not measured" except local generation, which says `$0` and points at the report file.

README includes the fine-tune command as a later step, not as something that was run:

```bash
CUDA_VISIBLE_DEVICES=0 python gr00t/experiment/launch_finetune.py \
  --base-model-path nvidia/GR00T-N1.7-3B \
  --dataset-path out/datasets/hero_kitchen \
  --embodiment-tag NEW_EMBODIMENT \
  --modality-config-path <to-be-written> \
  --num-gpus 1 \
  --output-dir out/checkpoints/gr00t \
  --max-steps 2000 \
  --global-batch-size 32
```

Next to that command, write: do not run this while `joints_are_placeholder` is true.

## T14 — final check

Run the definition-of-done commands in [02-mvp-tonight.md](02-mvp-tonight.md) except leave `serve` running only long enough to curl `/` and `/rooms/hero_kitchen`. Stop the server. Do not commit `out/`.

Done when: pytest is green, both validates are green, and `git status` shows no files under `out/`.

## Stop

After T14, stop. Do not start MimicGen, splat training, Cosmos, people, drawers, or a fine-tune.
