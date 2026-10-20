# Reference

Detailed usage for Arrival. The overview is in the [README](../README.md).

## Honest label: the `demo` dataset

These bullets are about the `demo` dataset (`out/datasets/<room>`). The MuJoCo `sim` dataset is described under [Simulation (MuJoCo)](#simulation-mujoco) and carries its own flags in `meta/info.json`.

- The dataset folder is a real GR00T LeRobot v2 layout (parquet, mp4, `meta/*.json`).
- **The motion inside it is a scripted placeholder in simulation.** It comes from `arrival_generator = "scripted_retarget"`: seed trajectories retargeted to new object poses. It is **not physically valid**: the `demo` path uses no MuJoCo and no contact physics. It is **not MimicGen** output.
- Frames are 64×64 `sim_texture` schematics. **No Gaussian splat** is trained or composited.
- **No GR00T training** was run, and there is **no real-robot result**.
- `meta/info.json` records `"arrival_physically_valid": false`. `meta/embodiment.json` records `"joints_are_placeholder": true`, because the `single_arm` joint values are zeros until a physics generator fills them.
- **Do not fine-tune GR00T (or any policy) on this data while `arrival_physically_valid` is false or `joints_are_placeholder` is true.**

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"        # demo, page, tests
python -m pip install -e ".[dev,sim]"    # + MuJoCo for `python -m arrival sim`
python -m pytest -q
```

## Run

Smoke demo, 4 episodes, under a minute:

```bash
python -m arrival demo --episodes 4
python -m arrival validate out/datasets/hero_kitchen
```

The full demo writes 1,000 successful episodes covering both task families, with an mp4 for every episode (about 30 s on a laptop):

```bash
python -m arrival demo --episodes 1000
python -m arrival validate out/datasets/hero_kitchen
```

`--videos` defaults to `all`, which is what GR00T's loader needs. `--videos sparse` or `none` drops the video feature from the dataset and writes human-only previews to `out/datasets/<room>_previews/`.

Open the page:

```bash
python -m arrival serve        # http://127.0.0.1:8000
python -m arrival serve --host 0.0.0.0   # reachable from the iOS capture app on the same Wi-Fi; prints the LAN URL
```

| Route | What it does |
|---|---|
| `GET /` | Lists rooms under `scans/` with `geometry_source`, task counts per family, dataset path, and download link. Has an upload form |
| `GET /rooms/<id>` | Fixtures, the two task families, `arrival_physically_valid`, and the run report |
| `GET /download/<id>` | Zip of `out/datasets/<id>` |
| `POST /jobs` | Multipart upload with file field `scan` (max 200 MB, larger gets 413). Writes `out/jobs/<id>/` and returns `202 {"status":"queued",...}`. Nothing is compiled or generated in the request; `python -m arrival work` drains the queue |
| `GET /jobs/<id>` | The job's `status.json` |
| `GET /jobs/<id>/download` | `out/jobs/<id>/dataset.zip` once the job is `done`, else 404 with the current status |
| `GET /previews/<file>` | A png, mp4 or gif from `out/previews/` (what `sim --save-preview` writes), with `Range` support so browsers can seek video |

The index page shows a card per room (stats and the latest preview), a drag-and-drop upload with a progress bar, and every job under `out/jobs/` with its status, stage bar, room id, episode count and a download link; running jobs refresh live. The server binds `127.0.0.1` by default and has no authentication. `--host 0.0.0.0` opens it to the local network for the capture app (`ios/README.md`); do that only on a network you trust. Uploads are streamed to a temp file and downloads are streamed too; a body shorter than `Content-Length`, a missing closing boundary, an empty file, or a part with no filename gets 400. If `out/datasets/<room>_sim` exists, the room page links it and shows its `arrival_generator`, `arrival_physically_valid`, episode count and families.

From a RoomPlan export instead of the authored scan (`scans/<room>/roomplan.json`):

```bash
python -m arrival demo --room hero_kitchen --from-roomplan --episodes 4
```

The normalizer unwraps Apple's keyed enums (`{"sink": {}}` -> `sink`, `washerDryer` -> `washer_dryer`), drops `low`-confidence objects, puts the floor at z = 0 (from `floors[]`, else the lowest wall bottom), rotates the room so its longest wall runs along +X with the wall bounding box at (0, 0), and snaps near-90° yaws. RoomPlan captures no small objects, so a mug, a bowl, a plate, a cup and an apple are placed (seeded, each at a seeded size within 8% of its catalog size; one that does not fit the counter is skipped) on the counter nearest a sink; nothing is borrowed from the authored scan. A scan with no sink, stove or counter-like fixture yields no tasks and the command says so. `--scans` defaults to `./scans`, falling back to the repo's `scans/` when run from elsewhere.

Doors, windows and openings are kept in the bundle and twin with the id of their wall, `polygonCorners` floors set the floor extent, and a merged multi-story export yields one story (`roomplan.load(path, room, story=n)`; default the story with the most objects). To eyeball every room as a top-down plan:

```bash
python scripts/render_rooms.py                              # out/renders/<room>_top.png and <room>_roomplan_top.png
python scripts/render_rooms.py tests/fixtures/roomplan/amal.json
```

## One-command demo

```bash
python scripts/demo_all.py --quick     # 2 episodes, 1 person, 64 px; --full is 8, 2, 128
python scripts/demo_all.py --room hero_kitchen --out out/demo --serve
```

Runs scan and compile, twin layout PNG, sim dataset, validate, scripted-expert eval and contact sheet, prints PASS or FAIL per stage, and writes `<out>/demo_summary.md` and `demo_summary.json`. Exits 1 if a stage fails. See `docs/ref/DEM-4.md`.
To land a new real scan (CAP-3a), `scripts/intake_scan.py` creates `scans/<room_id>/`, strips EXIF from the photos, writes `notes.md` and `measurements.json`, runs the geometry checks and prints GO or NO-GO (exit 0, 1, or 2 when an input is refused):

```bash
python scripts/intake_scan.py kitchen_01 --roomplan roomplan.json --photos a.jpg b.jpg --location-type kitchen \
    --phone "iPhone 15 Pro" --ios 18.1 --lighting daylight --clutter low \
    --measure counter_length=3.20,counter_height=0.92,sink_width=0.55   # also --no-photos, --scans DIR, --out DIR
```

`arrival.scan.intake.validate_scan_dir(path)` lists what is still missing. Details in `docs/ref/CAP-3a.md`.
To check the twin against tape measurements, put a `measurements.json` beside a room's `scan.json` (format and extraction rules in `docs/ref/TWN-1a.md`) and run `python scripts/scan_accuracy.py [scans/<room> ...]`: it prints the signed error per dimension and exits 1 when any is over `tolerance_m` (default 0.05 m); rooms without the file are skipped.

## Simulation (MuJoCo)

`python -m arrival sim --episodes N` builds a MuJoCo scene from the compiled twin and records episodes to `out/datasets/<room>_sim` (LeRobot v2 layout). Needs the `sim` extra. The code lives in `arrival/sim/`:

- **Articulated kitchen** from the twin: counters with drawers (slide joints), cabinet and wall-cabinet doors (hinge joints), a sink with a faucet lever, a stove with a bottom-hinged oven door, and fridge, dishwasher and microwave doors. `arrival.sim.scene.part_names(twin)` lists every joint with its handle site and an open position. Objects collide with the moving parts, so a mug rests on a drawer tray or an open oven door.
- **Arm**: a procedurally built 7-DoF Panda-like arm (not the Franka asset) driven through IK, so joint states in the dataset are the simulated joint positions, plus a parallel gripper that holds objects by friction contact.
- **Lighting and materials**: a key spot with shadows, a cool fill and a warm window light, scaled by the task's `lighting` label and jittered (level within 15%, colour temperature, key position, window side) by the task seed, so every episode in a label looks a little different and the labels never overlap in brightness. Surfaces use MuJoCo builtin textures tinted by the geom colour (tile floor, wood fronts, stone tops, backsplash boards, matte walls), so the scene still loads from a string with no asset files.
- **People**: kinematic proportioned bodies (seeded height and colours) with a leg and arm swing, walking seeded loops through the room: a free point, a lane that crosses behind the robot base, a 2 to 4 s stop at the counter, back out, every leg routed round the fixture footprints. The loop is laid out in the frame of the fixture the task works at, so it holds on any wall, and a room with no free strip in front of that fixture (the office scan) gets people on random free points and no counter stop (`sim` logs that per episode); the walk into a stop slows over its last 0.6 m so the swinging toe never reaches the counter. They move and occlude; they are not simulated humans and they do not collide. `arrival/sim/safety.py` measures the horizontal clearance between every robot collision geom and each person every control step; an episode whose minimum reaches 0 is a human contact and is dropped from the dataset even when the task succeeded. The value is written per episode as `arrival_min_human_distance_m` and `arrival_human_contact` in `meta/episodes.jsonl`.
- **Cameras**: ego and wrist views rendered with MuJoCo's offscreen renderer. `--res` (default 128) must be a multiple of 16; the writer rejects anything else before writing a file.
- **Policies** behind one interface: a scripted expert (default), a VLM planner via Nebius Token Factory (`--planner vlm`; needs `TOKEN_FACTORY_API_KEY`, falls back to the rule parser without one, and caches responses in `arrival/models/nemotron_cache.json`), and a VLA client for a GR00T policy server (placeholder; no server is shipped or run here).
- **Success is checked in physics** (object resting in the target region, drawer/door joint past threshold), not asserted by the script.

Run it:

```bash
python -m pip install -e ".[dev,sim]"
python -m arrival sim --episodes 8 --people 2 --save-preview   # contact sheet + mp4 in out/previews/
python -m arrival validate out/datasets/hero_kitchen_sim
python scripts/check_dataset_loader.py out/datasets/hero_kitchen_sim [--json]
```

`scripts/check_dataset_loader.py` is an offline stand-in for the GR00T loader (no `gr00t` import, details in `docs/ref/DAT-2a.md`). It exits 0 on pass and 1 on any failure, and refuses the placeholder `demo` dataset.

Status as of Oct 17 (scripted expert, friction grasps, physics-checked; 16/16 over these seven families with `--families all --episodes 16 --people 2 --seed 1` on a fresh clone):

| Family | Success | Note |
|---|---|---|
| `counter_to_sink` | 100% | mug, cup, apple and bottle by the body; bowl and plate by the rim; pan by its handle |
| `open_drawer` | 100% | both counters |
| `open_door` | 100% | both cabinet doors, 8/8 over two seeds; the door ends at about 70° (threshold 60°) |
| `counter_to_counter` | skipped | pick point and target about 2 m apart, base is fixed per episode. Needs a mobile base |
| `close_drawer` | 100% | starts open 0.30 m, pushed shut on the handle bar; success is the slide joint under 0.03 m |
| `close_door` | 100% | starts open 70°, pushed shut along its arc; success is the hinge under 5° |
| `put_in_drawer` | 100% | drawer starts open 0.14 m, mug set on the exposed part of the tray; success is the mug resting inside the tray |
| `wipe_counter` | 100% | sponge pinched and dragged two strokes; success needs 0.4 m travelled pressed to the top and the sponge back on it |
| `open_fridge` | 100% | 32/32 over two seeds, with and without people; the fingers close round the vertical bar and pull the door to 40°, then the closed fingertips push the inside face to 80° (threshold 60°). Not a default family |

Defaults are `counter_to_sink,open_drawer`. `--families all` runs every family; `counter_to_counter` is skipped with a log line until there is a mobile base (MAN-3), and any failed attempt is dropped and counted. Fixtures may stand on any wall: the base parks in the fixture's own frame, and before a task is built `arrival/sim/preflight.py` checks that its stand spot is inside the room, 0.15 m from every wall face and fixture, and that the pick, place and stroke points are within 0.745 m of the base (a geometric horizontal-reach test, not an IK solve, so a task that passes can still miss in physics). A rejected variation is logged with its reason and counted as `skipped_unreachable`; a task whose env build or rollout raises is logged (`SKIP at build|rollout: ...`), counted as `skipped_error`, and writes no episode. Skipped tasks are not attempts: `attempts` counts tasks that ran to the physics check and `dropped` those that failed it. The report (`out/reports/<room>_sim.json`) and `meta/info.json` carry `skipped`, `skipped_unreachable`, `skipped_error` and `skip_reasons` (at most 50; `arrival_` prefixed in `info.json`), `sim` prints them to stderr, and the worker status has `skipped`; when no task at all can run, the job fails with `error_kind: unsupported_layout` and the reasons in `error_reasons`, not a traceback. `--families` accepts every name in `SIM_FAMILIES` (`arrival/sim/tasks.py`) even though its `--help` text lists only four. `--planner vlm` sends each instruction through the Nemotron planner (POL-1), `--instructions nemotron --split train|eval` draws generated wordings with a held-out set (POL-2). `--tavily` adds appliance research to the twin and the planner prompt (see [Tavily research](#tavily-research)). The VLA client has never run against a real GR00T server; `python -m arrival.policy_server.mock_server --port 8000` is an offline stand-in that proves the plumbing only (see [ref/POL-3.md](ref/POL-3.md)).

### Closed-loop eval

```bash
python -m arrival eval --policy scripted --families counter_to_sink,open_drawer --episodes 4 --people 2
python -m arrival eval --holdout            # wording template 4 and the [0, +0.08] start offset (docs/07-eval.md)
python -m arrival eval --policy vla         # needs GR00T_POLICY_URL; exits 2 with a message when unset or unreachable
```

`eval` runs `--episodes` episodes per family through the same `SimEnv` and `run_episode` as `sim`, writes no dataset, prints a table, and writes `out/eval/<room>_<policy>.json` (shape in [04-contracts.md](04-contracts.md)). Per family: episodes, successes, success rate with a Wilson 95% interval, mean sim seconds (frames / 20), mean wall seconds, human contacts, the smallest robot-human distance seen, the largest IK residual, and arm-fixture contacts (`arm_contact_episodes`, `arm_contact_max_depth_m`). A human contact counts as a failure; an arm-fixture contact is counted, not scored. Every family ends through the same `finish_task` as `sim`, so the close and put families are covered, and an episode that raises is recorded as a failure instead of stopping the run. The eval is sim-in-the-twin only; nothing here scores a real robot.

`python -m arrival.generate.retarget` records one scripted-expert seed and replays it for new object start poses (`--attempts`, `--family counter_to_sink|counter_to_counter`, `--res`, `--seed`, `--baseline` to time the scripted expert on the same count). Successes (physics oracle) are written to `out/datasets/<room>_seed_replay/` with `arrival_generator = "seed_replay_retarget"` and a seed reference; unreachable or failed replays are dropped. Details in [ref/DAT-4a.md](ref/DAT-4a.md).

What this is not: MuJoCo frames are not a Gaussian splat of the room, episodes are not MimicGen output, and no policy was trained on them. Read `arrival_generator` and `arrival_physically_valid` in the sim dataset's `meta/info.json` before using it.

## Upload worker

`python -m arrival work` runs in a second terminal next to `serve`. It polls `out/jobs/*/status.json` every `--poll` seconds (default 2), takes the oldest `queued` job, marks it `running`, and runs these stages, rewriting `status.json` at each one: `normalize` (the upload is a RoomPlan CapturedRoom export if it has `walls`/`objects` with `transform`, or a `scan.json` if it has `schema_version`; anything else fails here), `twin` (`compile_twin`), `objects` (`place_default_objects` when the scan has no objects, as RoomPlan exports never do; then `out/twins/<room>/`), `sim` (`arrival.sim.collect.collect`, same options as `sim`: `--episodes 8`, `--families counter_to_sink,open_drawer`, `--people 1`, `--res 128`, `--seed 0`), `validate`, and `zip` (`out/jobs/<id>/dataset.zip` holding `<room>_sim/`). The room id is the upload's filename stem in `[a-z0-9_]` plus the job id, so two uploads of `kitchen.json` never share a twin or dataset folder. A job with zero successful episodes or a failing validator ends `failed`. Failures are written to `status.json` (`error`) and `error.txt` (traceback); the worker then moves to the next job. A job left `running` by a killed worker goes back to `queued` when the next worker starts (so do not start a second worker while one runs), and a job that raises mid-stage is recorded as `failed` with an `interrupted:` error. `status.json` is written atomically, so polls never see a torn file. `--once` processes at most one job and exits. Needs the `sim` extra; without MuJoCo every job fails at `sim`.

```bash
python -m arrival work                   # until Ctrl+C
python -m arrival work --once --episodes 2
```

Measured on a laptop CPU: a `scan.json` upload with `--episodes 2` took 5.9 s end to end, 2/2 episodes, 322 frames, zip 77,624 bytes. One worker runs at a time; there is no lock against two workers claiming the same job, no automatic retry of failed jobs, and nothing runs on Nebius (OPS-2).

## Tavily research

`python -m arrival research` looks up appliance specs (door and handle mechanisms, clearances, safety guidance) and caches the answers in `arrival/models/tavily_cache.json`, so repeat runs need no network. With no `TAVILY_API_KEY`, or when the call fails, it serves the cache and then a small built-in knowledge table; the source of each answer (`tavily_api`, `cache` or `fallback`) is printed.

```bash
python -m arrival research --room hero_kitchen             # appliances in the room's twin -> out/research/hero_kitchen_research.json
python -m arrival research --query "dishwasher door latch" # one direct query -> out/research/query_research.json
python -m arrival sim --tavily --episodes 2                # attach the research to the twin and the VLM planner prompt
```

Only appliance fixtures present in the twin are looked up (the sink counts; counters and walls are skipped). The research shapes the planner prompt and tags tasks `tavily_enriched`; it does not change the physics.

## Output layout

`out/` is gitignored. Nothing under it is committed.

```
out/
  twins/hero_kitchen/       twin.json, layout.yaml (RoboCasa subset), tasks.json
  datasets/hero_kitchen/    GR00T LeRobot v2
    meta/info.json          arrival_generator, arrival_physically_valid, arrival_successes, ...
    meta/tasks.jsonl
    meta/episodes.jsonl
    meta/modality.json      single_arm [0,7], gripper [7,8], ego_view, task description
    meta/embodiment.json
    meta/episodes_stats.jsonl, meta/stats.json
    meta/arrival_cartesian.jsonl   cartesian sidecar (eef/object traces)
    data/chunk-XXX/episode_XXXXXX.parquet   (1,000 episodes per chunk)
    videos/chunk-XXX/observation.images.ego_view/episode_XXXXXX.mp4
  datasets/hero_kitchen_sim/ MuJoCo sim dataset (same layout, ego_view + wrist videos)
  previews/                 sim contact sheets and overview mp4s (--save-preview)
  research/                 `research` output (<room>_research.json, query_research.json)
  reports/hero_kitchen.json attempts, successes, dropped, seconds, demos/hour, dollars
  eval/hero_kitchen_scripted.json   closed-loop eval: per-family success, Wilson 95%, time, human contacts
  jobs/<job_id>/            upload.bin, status.json; after `work`: dataset.zip (done) or error.txt (failed)
  twins/<stem>_<job_id>/, datasets/<stem>_<job_id>_sim/   what `work` compiled and simulated for an upload
```

The demo dataset's embodiment label is `robocasa_panda` (7 joints + 1 gripper, placeholder joints) and its two task families are `counter_to_sink` and `counter_to_counter`; the sim dataset is labelled `arrival_sim_panda` and lists its families in `arrival_families` (see the sim dataset notes in [04-contracts.md](04-contracts.md)). Both vary by object, start pose, lighting, and instruction wording.

## Credentials

The demo uses no credentials and makes no network calls, and neither do the tests. Token Factory (Nemotron planner and wordings) reads the variables below, and only inside `arrival.models.token_factory`; Tavily and the VLA client read their own:

| Variable | Purpose |
|---|---|
| `TOKEN_FACTORY_API_KEY` | Bearer token |
| `TOKEN_FACTORY_BASE_URL` | Defaults to `https://api.tokenfactory.nebius.com/v1`. Check it against the live docs |
| `NEMOTRON_OMNI_MODEL`, `NEMOTRON_ULTRA_MODEL`, `NEMOTRON_SUPER_MODEL`, `NEMOTRON_LIGHTNING_MODEL` | Optional model ids |
| `TAVILY_API_KEY`, `TAVILY_BASE_URL` | Optional, for `research` and `sim --tavily`; read only in `arrival.models.tavily`. Base URL defaults to `https://api.tavily.com/search` |
| `GR00T_POLICY_URL` | Address of a GR00T policy server, for `--policy vla` |

Export them in your shell, or put them in an untracked `.env` (gitignored) in the repo root or cwd: `arrival.models.token_factory` and `arrival.models.tavily` each read it themselves (cwd first, then the repo root), only when their own key is unset, and never override variables already set. No other module loads `.env`. Never commit keys. Account links and what to request are in [docs/08-access.md](08-access.md).

## Cost

`python -m arrival.eval.cost [--out out] [--usage usage.json] [--pricing configs/pricing.example.yaml] [--baseline teleop_baseline.json] [--json]` turns `out/reports`, `out/eval` and finished job statuses into demos per hour, seconds per successful demo and drop rate, with dollar rows that stay null unless a usage file gives units, and a generated-vs-teleop comparison only when a valid teleop baseline exists (`docs/ref/OPS-3a.md`). The pricing rates in `configs/pricing.example.yaml` are assumed, not invoiced.

None of the Nebius products below were called. Token Factory calls from `--planner vlm` and `--instructions nemotron` are not metered here either. The only measured number is the local generation run, which cost $0 on a laptop CPU. That says nothing yet about how generated data compares with teleoperation, because the comparison has not been measured.

| Step | Nebius product | Measured USD |
|---|---|---|
| Read the scan | Token Factory, Nemotron 3 Nano Omni | not measured |
| Assemble the twin, fill gaps | Token Factory, Nemotron 3 Ultra | not measured |
| Propose tasks | Token Factory, Nemotron 3 Super | not measured |
| Wordings | Nemotron 3.5 Lightning | not measured |
| People and episode labels | Nemotron 3.5 Lightning | not measured |
| Build the twin and appearance | Serverless AI Job, 1 GPU | not measured |
| Generate demos | Serverless AI Jobs, many | not measured (local generation: $0, see `out/reports/hero_kitchen.json`) |
| Restyle frames | Serverless Endpoint, Cosmos 3 | not measured |
| Fine-tune | Serverless AI Job, H100, GR00T N1.7 | not measured |
| Store artifacts | Object Storage | not measured |
| Host the app | Serverless Endpoint, CPU | not measured |

## Later: GR00T fine-tune (not run)

This step comes later. It was **not** run, and nothing in this repo was trained. **Do not run this while `joints_are_placeholder` is true** (or while `arrival_physically_valid` is false). It needs 40 GB+ VRAM and the Isaac-GR00T repo:

```bash
CUDA_VISIBLE_DEVICES=0 python gr00t/experiment/launch_finetune.py \
  --base-model-path nvidia/GR00T-N1.7-3B \
  --dataset-path out/datasets/hero_kitchen_sim \
  --embodiment-tag NEW_EMBODIMENT \
  --modality-config-path configs/gr00t/arrival_panda_config.py \
  --num-gpus 1 \
  --output-dir out/checkpoints/gr00t \
  --max-steps 2000 \
  --global-batch-size 32
```

The modality config is `configs/gr00t/arrival_panda_config.py` (arm trained as relative joint deltas, gripper absolute, 16-step action horizon). `tests/test_gr00t_config.py` checks its keys against the `meta/modality.json` that `arrival sim` writes, with GR00T stubbed out. Not yet checked: that GR00T's own loader reads the dataset (needs the Isaac-GR00T install and a GPU box) and that its stats files compute without NaNs.

### Appearance variation (offline)

`python -m arrival.render.variation SRC_DATASET NEW_COPY_DIR [--backend local_stub|cosmos] [--seed N] [--fraction 0.1]` copies a sim dataset and restyles about 10% of its frames; the source is untouched. Writes `meta/arrival_variation.jsonl`, `meta/arrival_variation_summary.json`, `variation_videos/`, and sets `arrival_appearance_variation` in the copy's `info.json` to `cosmos` (only after a real Cosmos success), `local_stub` or `none`. `cosmos` reads `COSMOS_URL`; without it every selected frame is reported as skipped and stays original. Added latency and cost are reported as null. See [ref/SIM-7a.md](ref/SIM-7a.md).

## Known gaps

Not built yet, and not claimed anywhere in the outputs:

- Field-tested iPhone capture. The app exists (`ios/`, CAP-1) and uploads to `POST /jobs`, but no real kitchen scanned with it is checked in yet. Uploads are processed only by a local `python -m arrival work` process.
- MimicGen generation (`arrival/generate/mimicgen.py` is a stub).
- Gaussian splat training or compositing (`arrival/render/splat.py` is a stub).
- Cosmos restyle of frames.
- Nebius Serverless fan-out of generation jobs.
- GR00T fine-tune (command above, not run). `python -m arrival eval` scores policies in the sim; it has only been run with the scripted expert.
- RoboCasa-native layout conventions: `layout.yaml` is a subset emitter (world-frame `pos`, `z_rot` on oblique walls), not loadable by RoboCasa as-is.

