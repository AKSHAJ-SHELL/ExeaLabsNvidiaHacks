# Arrival

**Scan a room once. Get robot training data for that exact room.**

[![Arrival demo: scan → digital twin → MuJoCo simulation → GR00T dataset](docs/media/demo.gif)](docs/media/demo.mp4)

*30-second demo, rendered from the real code. Click for the full-quality mp4. Regenerate it with `python scripts/make_demo_video.py`.*

---

## What this is

General robot policies like NVIDIA GR00T are trained on generic kitchens. When a robot arrives in *your* kitchen, it has never seen your counters, your sink or your drawers. Arrival closes that gap:

1. **Scan.** An iPhone LiDAR scan (Apple RoomPlan) describes the room: walls, counters, sink, stove, fridge.
2. **Twin.** We compile the scan into a digital twin: a RoboCasa-style layout and a MuJoCo scene with working drawers and doors.
3. **Simulate.** A 7-joint Panda-style arm does tasks in the twin while people walk around. Grasps use friction physics, and success is checked by the simulator.
4. **Capture.** Every successful episode is written as a [GR00T](https://github.com/NVIDIA/Isaac-GR00T)-compatible LeRobot v2 dataset: joint states, actions, ego and wrist camera video, and language instructions.
5. **Fine-tune** *(next)*. Train GR00T N1.7 on that room's data so the robot is useful on day one.

Built for the NVIDIA × Nebius hackathon by Exea Labs and a team of about 35. The product spec is [plan.pdf](plan.pdf).

## Does it work? (status, Oct 14 2026)

| Stage | Status |
|---|---|
| Scan → twin | ✅ Works on the sample kitchen and on 2 real public iPhone RoomPlan exports. ⚠️ No iPhone capture app yet |
| Simulation: kitchen, drawers, doors, people | ✅ Works. MuJoCo, built from the twin |
| Robot: pick mug → sink | ✅ 100% success, friction grasp, physics-checked |
| Robot: open drawer | ✅ 100% success |
| Robot: open door | ❌ 0%. The arm's arc path doesn't move the door yet ([help wanted](#help-wanted)) |
| Robot: counter → counter | ❌ Skipped. The counters are 2.2 m apart and the base doesn't move |
| GR00T-format dataset + validator | ✅ Passes our validator, and the layout matches GR00T's loader source. ⚠️ Not yet loaded by GR00T itself since the latest fixes |
| Local web page: browse, download, upload | ✅ Works. ⚠️ Uploads are queued; nothing processes them yet |
| VLM planner (Nemotron) / VLA client (GR00T server) | ⚠️ The interfaces exist. Neither is wired in or tested against a live service |
| GR00T fine-tune, MimicGen, splats, Cosmos, Nebius scale-out | ❌ Not built yet |

There are two datasets. `python -m arrival sim` writes **physics-simulated** data with real joint states (`arrival_physically_valid: true`). `python -m arrival demo` writes a fast **scripted placeholder** with zero joint values (`arrival_physically_valid: false`). Never train on the placeholder.

## Get started (5 minutes)

Requires Python 3.11+ on macOS or Linux. No GPU and no API keys needed.

```bash
git clone https://github.com/AvnehSBhatia/ExeaLabsNvidiaHacks.git
cd ExeaLabsNvidiaHacks
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev,sim]"
python -m pytest -q                       # should be all green
```

Run the simulation and look at what it recorded:

```bash
python -m arrival sim --episodes 8 --people 2 --save-preview
python -m arrival validate out/datasets/hero_kitchen_sim
open out/previews/                        # contact sheet + overview video
```

Then browse it in the local page:

```bash
python -m arrival serve                   # http://127.0.0.1:8000
```

Other commands:

```bash
python -m arrival demo --episodes 1000                         # fast scripted placeholder dataset
python -m arrival demo --room hero_kitchen --from-roomplan     # build from a RoomPlan JSON export
python -m arrival sim --families all                           # include the not-yet-working tasks
```

Full usage, output layout, credentials and cost tracking are in **[docs/REFERENCE.md](docs/REFERENCE.md)**.

## How it works

```
iPhone LiDAR scan (RoomPlan JSON)          scans/<room>/roomplan.json
        │  arrival/scan        normalize: Apple enums, floor at z=0, align walls
        ▼
Digital twin                               out/twins/<room>/twin.json, layout.yaml
        │  arrival/twin        fixtures → RoboCasa types, synthesize counters
        │  arrival/tasks       tasks × objects × poses × lighting × wordings
        ▼
MuJoCo scene                               arrival/sim/scene.py
        │  drawers (slide joints), doors (hinges), sink basin, free objects
        │  people walking (arrival/sim/people.py), 3 cameras
        ▼
Robot + policy                             arrival/sim/robot.py, ik.py, policy.py
        │  7-DoF arm + gripper, IK, scripted expert │ VLM planner │ VLA client
        ▼
Physics success check → drop failures      arrival/sim/collect.py
        ▼
GR00T LeRobot v2 dataset                   out/datasets/<room>_sim/
        │  arrival/export      parquet + mp4 + meta, validator
        ▼
Fine-tune GR00T N1.7 (next)                docs/REFERENCE.md#later-gr00t-fine-tune-not-run
```

| Folder | What lives there |
|---|---|
| `arrival/scan/` | Scan loaders: RoomPlan JSON, authored ScanBundle, four-photo slot |
| `arrival/twin/`, `arrival/catalog/` | Twin compiler and category maps |
| `arrival/tasks/` | Task and variation proposer |
| `arrival/sim/` | MuJoCo scene, robot, IK, people, policies, data collection |
| `arrival/export/` | LeRobot v2 writer and validator |
| `arrival/generate/`, `arrival/render/` | Scripted placeholder generator, schematic renderer, MimicGen and splat stubs |
| `arrival/models/` | Nebius Token Factory (Nemotron) client |
| `arrival/web/`, `arrival/jobs/` | Local web page and upload queue |
| `scans/` | Sample rooms |
| `tests/` | pytest suite. No network, runs in about 15 s |
| `docs/` | Reference, design contracts, access links, build log |

## Join in

There are about 35 of us, so we split into workstreams. Pick one, tell the team channel, and grab a task.

| Workstream | What you'd build | Start in |
|---|---|---|
| **Capture** | iPhone app: Apple RoomPlan sample + JSON export + RGB-D frames; scan real kitchens | `arrival/scan/`, `tests/fixtures/roomplan/` |
| **Twin** | RoboCasa-native layout conventions, doors/windows from RoomPlan, more fixture types | `arrival/twin/`, `arrival/catalog/` |
| **Manipulation** | Fix door opening, add a mobile base for counter→counter, grasp the bowl, new tasks | `arrival/sim/policy.py`, `collect.py` |
| **People & realism** | Better human motion, Cosmos restyle, Gaussian splat appearance | `arrival/sim/people.py`, `arrival/render/` |
| **Policy (VLA/VLM)** | Wire the Nemotron planner into collection, run a GR00T policy server, closed-loop eval | `arrival/sim/policy.py`, `arrival/models/` |
| **Data & training** | GR00T modality config, fine-tune smoke test on H100, MimicGen | `arrival/export/`, `arrival/generate/` |
| **Scale on Nebius** | Upload worker, Serverless Jobs fan-out, Object Storage, cost tracking | `arrival/jobs/`, `arrival/eval/` |
| **Demo & web** | Hosted page, dataset viewer, pitch video | `arrival/web/`, `scripts/` |

### Help wanted

Good first tasks, roughly in priority order:

1. **Make `open_door` succeed.** It's 0% now. See the door path in `arrival/sim/policy.py`, and test with `python -m arrival sim --families open_door --episodes 4 --save-preview`.
2. **Mobile base** so `counter_to_counter` is reachable.
3. **Scan a real kitchen with a LiDAR iPhone** and add it under `scans/<your_room>/roomplan.json`.
4. **GR00T modality config** plus a 100-step fine-tune smoke test on the sim dataset.
5. **Wire `VLMPlanner` into `collect()`** using a Token Factory key ([docs/08-access.md](docs/08-access.md)).
6. **Upload worker** that turns a queued scan into a twin and a sim dataset.

### How to contribute

1. **Work on a branch and open a PR into `main`**, e.g. `feat/sim-door-opening`. Keep PRs small, with one module per PR.
2. **Run `python -m pytest -q` before you push.** If you touch data, also run `sim` or `demo` and then `validate`.
3. **Follow the schemas** in [docs/04-contracts.md](docs/04-contracts.md). Don't invent parallel formats.
4. **Keep the labels honest.** `arrival_physically_valid`, `arrival_generator` and `joints_are_placeholder` must describe what really happened. Never call scripted data MimicGen, trained, or real-robot.
5. **Never commit secrets or `out/`.** Put API keys in `.env`, which is gitignored. See [docs/REFERENCE.md#credentials](docs/REFERENCE.md#credentials).

## Docs

- [docs/REFERENCE.md](docs/REFERENCE.md): every command, output layout, credentials, cost table, fine-tune command
- [docs/08-access.md](docs/08-access.md): Nebius, Token Factory, GR00T and RoboCasa accounts and links
- [docs/04-contracts.md](docs/04-contracts.md): data schemas
- [docs/09-later.md](docs/09-later.md): designs for MimicGen, splat, Cosmos and fine-tune
- [docs/BUILD-LOG.md](docs/BUILD-LOG.md): what changed and why
- [docs/00-START-HERE.md](docs/00-START-HERE.md): the original MVP build contract

## License

Apache 2.0. See [LICENSE](LICENSE). Copyright 2026 Exea Labs.
