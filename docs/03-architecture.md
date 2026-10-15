# Architecture

One scan becomes a dataset. Tonight every box below exists as a Python module. Only the solid path runs.

```
scan bundle
  -> normalize (RoomPlan JSON or four-photo slot)
  -> twin (fixture boxes + RoboCasa-subset YAML)
  -> tasks (two families, four variation axes)
  -> seeds + retarget
  -> oracle (drop failures)
  -> sim_texture frames
  -> GR00T LeRobot v2
  -> local page + queued upload
```

Later boxes, present only as modules that raise a named error or return a skipped probe: Token Factory calls, splat composite, MimicGen, Cosmos, GR00T fine-tune, Serverless fan-out.

## Modules

| Module | Responsibility |
|---|---|
| `arrival.scan.bundle` | Load and validate a ScanBundle |
| `arrival.scan.roomplan` | CapturedRoom JSON → ScanBundle, Y-up to Z-up |
| `arrival.scan.four_photo` | Four images → ScanBundle flagged unmeasured |
| `arrival.twin.compile` | ScanBundle → layout dict + YAML |
| `arrival.catalog.fixtures` | RoomPlan category → RoboCasa fixture type or `box` |
| `arrival.catalog.objects` | Object label → catalog id |
| `arrival.tasks.propose` | Tasks, variations, wordings. No network |
| `arrival.generate.scripted` | Seed trajectories and pose retargets |
| `arrival.generate.oracle` | Drop attempts that miss the goal |
| `arrival.generate.mimicgen` | Import probe. Skip if RoboCasa is absent |
| `arrival.render.sim_texture` | 64×64 RGB frames from episode cartesian traces |
| `arrival.render.splat` | Raises `SplatCompositeNotImplemented` |
| `arrival.export.lerobot` | Parquet, mp4, meta |
| `arrival.export.validate` | Structural checker. Does not import GR00T |
| `arrival.eval.report` | Speed and cost report |
| `arrival.models.token_factory` | OpenAI-compatible client. Unused by the demo |
| `arrival.jobs.queue` | Write `out/jobs/<id>/status.json` |
| `arrival.web.app` | `ThreadingHTTPServer` routes |
| `arrival.cli` | `demo`, `validate`, `serve` |

## Data flow for `arrival demo`

1. Load `scans/hero_kitchen/scan.json`.
2. Compile `out/twins/hero_kitchen/layout.yaml` and `twin.json`.
3. Propose tasks to `out/twins/hero_kitchen/tasks.json`.
4. Generate attempts. Every 10th attempt (indexes 9, 19, …) is a miss: the gripper stays open. The oracle drops misses.
5. Keep going until `successes == --episodes` or attempts hit `episodes * 2`, whichever first. Attempt indexes 9, 19, 29, … are misses. Reaching 1,000 successes takes 1,111 attempts and 111 drops. Use RNG seed 0.
6. Render frames for episodes included by the video policy.
7. Write the LeRobot folder and `out/reports/hero_kitchen.json`.

Video policy:

- `--videos all`: an mp4 for every successful episode.
- `--videos sparse` (required for the 1,000 run): an mp4 when `episode_index % 125 == 0`, so episodes 0, 125, …, 875 (8 files).
- `--videos none`: no mp4. Validator then requires `info.json` field `walkin_video_policy = "none"`. The done command does not use this.

## Composite renderer (specified, not run)

This is the spec's step 5. Implement it later behind `arrival.render.splat`. Do not fake it tonight.

For each robot camera pose at each frame:

- Splat supplies RGB and depth for the static room.
- The simulator supplies RGB and depth for the robot, the grasped object, and any moving fixture. Its background is empty.
- Output pixel is the simulator pixel where simulator depth is closer than splat depth by more than `0.01` m. Otherwise the splat pixel.

`sim_texture` draws the whole frame and records `appearance = "sim_texture"`.

## Web

Single process. No authentication. Bind `127.0.0.1` only. Uploaded bytes are stored under `out/jobs/<id>/upload.bin` with a max size of 200 MB. Oversize returns HTTP 413. The status JSON is the whole API. There is no worker loop that drains the queue tonight.

## Nebius mapping

The spec assigns products. Tonight none of them are called. The README cost table still lists them so the later wiring has a place to put numbers.

| Step | Product | Tonight |
|---|---|---|
| Read the scan | Token Factory, Nemotron 3 Nano Omni | Deterministic catalog |
| Assemble the twin, fill gaps | Token Factory, Nemotron 3 Ultra | Compiler only, no gap fill |
| Propose tasks | Token Factory, Nemotron 3 Super | Templates |
| Wordings | Nemotron 3.5 Lightning | Four templates |
| People and episode labels | Nemotron 3.5 Lightning | Not built |
| Build the twin and appearance | Serverless AI Job, 1 GPU | Local compiler + sim_texture |
| Generate demos | Serverless AI Jobs, many | Local scripted retarget |
| Restyle frames | Serverless Endpoint, Cosmos 3 | Not built |
| Fine-tune | Serverless AI Job, H100, GR00T N1.7 | Not built |
| Store artifacts | Object Storage | Local `out/` |
| Host the app | Serverless Endpoint, CPU | Local `serve` |

## Coordinates

Internal frame is Z-up, meters, right-handed. Positions are box centers. Yaw is radians about Z. RoomPlan input is ARKit Y-up. Conversion is in [04-contracts.md](04-contracts.md) and is tested.
