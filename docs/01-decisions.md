# Locked decisions

These were confirmed by the user on Oct 14, 2026, then narrowed for a one-night MVP. If a later doc conflicts with this file, this file wins.

## Product

- New pipeline in this repo, with a four-photo input slot and an oracle that drops failed attempts.
- One hero kitchen. Capture assumption: one LiDAR iPhone scan will arrive later. Tonight the repo ships an authored sample that uses the same schema.
- LiDAR + Apple RoomPlan is the critical path. The four-photo path is accepted as input and must not block the demo.
- Proof is simulation of the scanned room. No real-robot number is promised. The before/after in any demo is a rollout in the twin, labeled as simulation.
- Judges click pre-scanned rooms. Upload writes a queued job and returns. It does not run the pipeline inside the HTTP request.
- Embodiment for generated data is RoboCasa's single arm (Panda, 7 joints + 1 gripper). Fine-tune target, later, is GR00T N1.7 if that embodiment is supported, otherwise the Nebius LeRobot cookbook policy. Tonight does not train either model.
- Variation axes on the critical path: object, start pose, lighting, instruction wording. People and Cosmos are off the critical path.
- Scale target of the generator: at least 1,000 successful episodes in the hero kitchen, both tasks. The default smoke command uses 4 episodes. The 1,000-episode command must be able to finish locally.

## MVP cuts (tonight only)

The user did not freeze these forever. They are cuts so the night has a finished slice. They are specified in [09-later.md](09-later.md) and must not be coded.

- Runnable tasks are the two from the spec: pick from counter and place in the sink, and move an object between counters. Drawers and doors are not scheduled.
- The checked-in scenario is a kitchen. Unrecognized RoomPlan categories still compile to `type: box`, so the non-kitchen path exists as a compiler rule, not as a second demo room.
- Appearance backend that runs is `sim_texture`. The splat composite is a module that refuses to pretend it rendered a splat.
- Apache 2.0 is still required, because the hackathon spec requires a public Apache 2.0 repo.
- The spec's calendar (Oct 19, Oct 24, Oct 27, Oct 30) is ignored. There is no go/no-go date in this handoff.

## Generator truthfulness

- Tonight's writer is `scripted_retarget`. It retargets a handful of seed trajectories to new object poses. It does not run MuJoCo.
- Every dataset records `arrival_generator` and `arrival_physically_valid`.
- Do not describe scripted episodes as MimicGen output.
- The MimicGen command from RoboCasa is documented in [09-later.md](09-later.md). A probe module may check whether `robocasa` imports. It must skip cleanly when it does not.

## Dependencies you may add

Python 3.11+. Runtime: `numpy`, `pyarrow`, `pyyaml`, `pillow`, `imageio`, `imageio-ffmpeg`. Tests: `pytest`. No web framework. Use the standard-library HTTP server. No MuJoCo, no RoboCasa, no Gaussian-splat trainer, no GPU library.
