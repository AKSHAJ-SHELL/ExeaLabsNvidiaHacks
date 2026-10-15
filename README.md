# WALK·IN Arrival

WALK·IN Arrival turns one room scan into robot demonstration data for that room. You give it a scan of a kitchen and it writes a [GR00T](https://github.com/NVIDIA/Isaac-GR00T)-shaped LeRobot v2 dataset of pick-and-place episodes in a simulated copy of the room. It also serves a small local page where you can browse rooms, download a dataset, and queue a new scan.

The repo ships one authored sample room, `scans/hero_kitchen/`, in the ScanBundle schema. `--from-roomplan` reads a subset of Apple's RoomPlan `CapturedRoom` JSON (keyed-enum categories, floors, walls, objects); the normalizer is tested against 2 public real exports in `tests/fixtures/roomplan/`. There is no iPhone capture app in this repo yet. Nebius credentials are not needed to run anything here.

## Honest label (read this first)

These bullets are about the `demo` dataset (`out/datasets/<room>`). The MuJoCo `sim` dataset is described under [Simulation (MuJoCo)](#simulation-mujoco) and carries its own flags in `meta/info.json`.

- The dataset folder is a real GR00T LeRobot v2 layout (parquet, mp4, `meta/*.json`).
- **The motion inside it is a scripted placeholder in simulation.** It comes from `walkin_generator = "scripted_retarget"`: seed trajectories retargeted to new object poses. It is **not physically valid**: the `demo` path uses no MuJoCo and no contact physics. It is **not MimicGen** output.
- Frames are 64×64 `sim_texture` schematics. **No Gaussian splat** is trained or composited.
- **No GR00T training** was run, and there is **no real-robot result**.
- `meta/info.json` records `"walkin_physically_valid": false`. `meta/embodiment.json` records `"joints_are_placeholder": true`, because the `single_arm` joint values are zeros until a physics generator fills them.
- **Do not fine-tune GR00T (or any policy) on this data while `walkin_physically_valid` is false or `joints_are_placeholder` is true.**

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

The full demo writes 1,000 successful episodes covering both task families. `--videos sparse` writes 8 mp4s (episodes 0, 125, …, 875) so the run fits the laptop time budget:

```bash
python -m arrival demo --episodes 1000 --videos sparse
python -m arrival validate out/datasets/hero_kitchen
```

Without `--videos`, runs of more than 16 episodes stop and ask you to pass `--videos sparse` or `--videos all`. This guards against an accidental giant encode.

Open the page:

```bash
python -m arrival serve        # http://127.0.0.1:8000
```

| Route | What it does |
|---|---|
| `GET /` | Lists rooms under `scans/` with `geometry_source`, task counts per family, dataset path, and download link. Has an upload form |
| `GET /rooms/<id>` | Fixtures, the two task families, `walkin_physically_valid`, and the run report |
| `GET /download/<id>` | Zip of `out/datasets/<id>` |
| `POST /jobs` | Multipart upload with file field `scan` (max 200 MB, larger gets 413). Writes `out/jobs/<id>/` and returns `202 {"status":"queued",...}`. Nothing is compiled or generated in the request, and no worker drains the queue yet |
| `GET /jobs/<id>` | The job's `status.json` |

The server binds `127.0.0.1` only and has no authentication. Uploads are streamed to a temp file; a body shorter than `Content-Length`, a missing closing boundary, an empty file, or a part with no filename gets 400. If `out/datasets/<room>_sim` exists, the room page links it and shows its `walkin_generator`, `walkin_physically_valid`, episode count and families.

From a RoomPlan export instead of the authored scan (`scans/<room>/roomplan.json`):

```bash
python -m arrival demo --room hero_kitchen --from-roomplan --episodes 4
```

The normalizer unwraps Apple's keyed enums (`{"sink": {}}` -> `sink`, `washerDryer` -> `washer_dryer`), drops `low`-confidence objects, puts the floor at z = 0 (from `floors[]`, else the lowest wall bottom), rotates the room so its longest wall runs along +X with the wall bounding box at (0, 0), and snaps near-90° yaws. RoomPlan captures no small objects, so a mug and a bowl are placed (seeded) on the counter nearest a sink; nothing is borrowed from the authored scan. A scan with no sink, stove or counter-like fixture yields no tasks and the command says so. `--scans` defaults to `./scans`, falling back to the repo's `scans/` when run from elsewhere.

## Simulation (MuJoCo)

`python -m arrival sim --episodes N` builds a MuJoCo scene from the compiled twin and records episodes to `out/datasets/<room>_sim` (LeRobot v2 layout). Needs the `sim` extra. The code lives in `arrival/sim/`:

- **Articulated kitchen** from the twin: counters, sink, stove, fridge, cabinets, with drawers on slide joints and doors on hinge joints.
- **Arm**: a procedurally built 7-DoF Panda-like arm (not the Franka asset) driven through IK, so joint states in the dataset are the simulated joint positions, plus a parallel gripper that holds objects by friction contact.
- **People**: kinematic bodies walking scripted paths through the room. They move and occlude; they are not simulated humans.
- **Cameras**: rendered with MuJoCo's offscreen renderer.
- **Policies** behind one interface: a scripted expert (default), a VLM planner via Nebius Token Factory (needs `TOKEN_FACTORY_API_KEY`; placeholder until a key is set), and a VLA client for a GR00T policy server (placeholder; no server is shipped or run here).
- **Success is checked in physics** (object resting in the target region, drawer/door joint past threshold), not asserted by the script.

Run it:

```bash
python -m pip install -e ".[dev,sim]"
python -m arrival sim --episodes 8 --people 2 --save-preview   # contact sheet + mp4 in out/previews/
python -m arrival validate out/datasets/hero_kitchen_sim
```

Status as of Oct 14 (scripted expert, friction grasps, physics-checked):

| Family | Success | Note |
|---|---|---|
| `counter_to_sink` | 100% | mug only; the bowl is wider than the gripper |
| `open_drawer` | 100% | both counters |
| `open_door` | 0% | arc trajectory doesn't move the door yet. **Help wanted** |
| `counter_to_counter` | skipped | targets ~2.2 m apart, base is fixed per episode. Needs a mobile base |

Defaults are `counter_to_sink,open_drawer`. `--families all` includes the broken ones (their failures are dropped and counted). The VLM planner is not yet wired into `collect()`, and the VLA client has never run against a real GR00T server.

What this is not: MuJoCo frames are not a Gaussian splat of the room, episodes are not MimicGen output, and no policy was trained on them. Read `walkin_generator` and `walkin_physically_valid` in the sim dataset's `meta/info.json` before using it.

## Output layout

`out/` is gitignored. Nothing under it is committed.

```
out/
  twins/hero_kitchen/       twin.json, layout.yaml (RoboCasa subset), tasks.json
  datasets/hero_kitchen/    GR00T LeRobot v2
    meta/info.json          walkin_generator, walkin_physically_valid, walkin_successes, ...
    meta/tasks.jsonl
    meta/episodes.jsonl
    meta/modality.json      single_arm [0,7], gripper [7,8], ego_view, task description
    meta/embodiment.json
    data/chunk-000/episode_XXXXXX.parquet
    videos/chunk-000/observation.images.ego_view/episode_XXXXXX.mp4
  reports/hero_kitchen.json attempts, successes, dropped, seconds, demos/hour, dollars
  jobs/<job_id>/            upload.bin, status.json
```

Embodiment is RoboCasa's single-arm Panda (7 joints + 1 gripper). The two task families are `counter_to_sink` and `counter_to_counter`. They vary by object, start pose, lighting, and instruction wording.

## Credentials

The demo uses no credentials and makes no network calls. Later Nebius Token Factory wiring reads these environment variables, and only inside `arrival.models.token_factory`:

| Variable | Purpose |
|---|---|
| `TOKEN_FACTORY_API_KEY` | Bearer token |
| `TOKEN_FACTORY_BASE_URL` | Defaults to `https://api.tokenfactory.nebius.com/v1`. Check it against the live docs |
| `NEMOTRON_OMNI_MODEL`, `NEMOTRON_ULTRA_MODEL`, `NEMOTRON_SUPER_MODEL`, `NEMOTRON_LIGHTNING_MODEL` | Optional model ids |

Export them in your shell, or put them in an untracked `.env` (gitignored) in the repo root or cwd: `arrival.models.token_factory` reads it itself, only when `TOKEN_FACTORY_API_KEY` is unset, and never overrides variables already set. No other module loads `.env`. Never commit keys. Account links and what to request are in [docs/08-access.md](docs/08-access.md).

## Cost

None of the Nebius products below were called. The only measured number is the local generation run, which cost $0 on a laptop CPU. That says nothing yet about how generated data compares with teleoperation, because the comparison has not been measured.

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

This step comes later. It was **not** run, and nothing in this repo was trained. **Do not run this while `joints_are_placeholder` is true** (or while `walkin_physically_valid` is false). It needs 40 GB+ VRAM and the Isaac-GR00T repo:

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

## Known gaps

Not built yet, and not claimed anywhere in the outputs:

- iPhone capture app (LiDAR + RoomPlan) and an upload worker; `POST /jobs` only queues.
- MimicGen generation (`arrival/generate/mimicgen.py` is a stub).
- Gaussian splat training or compositing (`arrival/render/splat.py` is a stub).
- Cosmos restyle of frames.
- Nebius Serverless fan-out of generation jobs.
- GR00T fine-tune (command above, not run) and any policy evaluation.
- RoboCasa-native layout conventions: `layout.yaml` is a subset emitter (world-frame `pos`, `z_rot` on oblique walls), not loadable by RoboCasa as-is.

## Repo map

| Path | What |
|---|---|
| `scans/hero_kitchen/` | Authored sample scan (`scan.json`, `roomplan.json`) |
| `arrival/scan/` | ScanBundle loader, RoomPlan (Apple keyed enums, floor offset, room alignment, Y-up to Z-up), four-photo slot (flagged unmeasured) |
| `arrival/catalog/`, `arrival/twin/` | Fixture/object maps, twin compiler, RoboCasa-subset `layout.yaml` |
| `arrival/tasks/` | Task proposer: two families, four variation axes, no network |
| `arrival/generate/` | Scripted retarget, oracle, MimicGen import probe (skips if absent) |
| `arrival/render/` | `sim_texture` frames. The splat module raises `SplatCompositeNotImplemented` |
| `arrival/export/` | LeRobot v2 writer and structural validator |
| `arrival/eval/` | Speed and cost report |
| `arrival/models/` | Token Factory client, unused by the demo |
| `arrival/jobs/`, `arrival/web/` | Upload queue and stdlib HTTP server |
| `arrival/cli.py` | `demo`, `validate`, `serve` |
| `tests/` | pytest suite, no network |
| `docs/` | Build contract. Start at [docs/00-START-HERE.md](docs/00-START-HERE.md) |

## How to contribute

This repo is built by a hackathon team of about 30 to 40 people. To keep that workable:

1. **Branch and open a PR.** Never push to `main`. Use a branch per change, e.g. `feat/<module>-<short-name>`, and open a pull request.
2. **Pick a module.** Take an item from [docs/09-later.md](docs/09-later.md), such as the MimicGen generator, the splat composite, Cosmos restyle, Token Factory calls, Serverless fan-out, or a real RoomPlan scan. Say in the team channel or on the PR that you're taking it, so two people don't build the same thing. Keep changes inside that module and follow the schemas in [docs/04-contracts.md](docs/04-contracts.md). Don't invent parallel formats.
3. **Run the tests before you open the PR.** `python -m pytest -q` must pass. If you touch generation or export, also run `python -m arrival demo --episodes 4 && python -m arrival validate out/datasets/hero_kitchen`.
4. **Keep the label honest.** Flip `walkin_physically_valid` or `joints_are_placeholder` only when the data really is physically valid and the joints really are real. Never describe scripted episodes as MimicGen, splat, trained, or real-robot results.
5. **No secrets and no `out/`** in commits.

Decisions in [docs/01-decisions.md](docs/01-decisions.md) are locked for the MVP. Open an issue before reopening one.

## More

- [docs/00-START-HERE.md](docs/00-START-HERE.md): the build contract
- [docs/08-access.md](docs/08-access.md): Nebius, Token Factory, GR00T, and RoboCasa links
- [docs/PRIOR-ART.md](docs/PRIOR-ART.md): what already existed in Walk-In and what is new here
- [plan.pdf](plan.pdf): product spec

Future work happens on a branch and a pull request.

## License

Apache License 2.0. See [LICENSE](LICENSE). Copyright 2026 Exea Labs.
