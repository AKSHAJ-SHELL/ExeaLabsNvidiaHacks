# Evaluation

Three measurements come from the spec. Tonight only the first one has numbers, and those numbers are for the scripted generator, not for teleoperation and not for MimicGen. The report schema is in [04-contracts.md](04-contracts.md). Leave `teleop_baseline`, `usefulness`, and `realism` as `null`.

## Speed and cost

Claim it supports: generated demonstrations are cheaper and faster than teleoperation.

How, when someone measures it for real:

- Count successful episodes and wall-clock seconds for a finished run.
- Dollars are the sum of Nebius invoices for that run, split by product: Token Factory, Serverless Jobs, Cosmos endpoint, Object Storage, app endpoint.
- Baseline: teleoperate the same task in the twin with RoboCasa's teleop tools, time 20 successes, and divide. That baseline is not part of tonight.

Tonight: fill successes, attempts, seconds, and demos per hour from the local run. Dollars stay unmeasured except local CPU at $0. The README must not convert that $0 into the claim "data is far cheaper." It may say the local placeholder cost $0 and the comparison is not yet measured.

## Usefulness

Claim it supports: the data teaches the room.

Protocol, later, in simulation of the scanned room only:

- Tasks: `counter_to_sink` and `counter_to_counter`.
- Held-out variations: object poses and wordings not used in training. Split by holding out wording template 4 and the start offset `[0, +0.08]`.
- Three cells, same held-out set, 50 episodes per cell:
  1. GR00T N1.7 base, no fine-tune.
  2. GR00T N1.7 fine-tuned on generic RoboCasa data.
  3. GR00T N1.7 fine-tuned on this room's dataset.
- Success: object within 0.05 m horizontally of the target point and released (gripper open at the end).
- If the gain of cell 3 over cell 2 is inside a 5 to 6 percent absolute band, report no gain. Do not fish for a seed that crosses the band.
- If GR00T N1.7 does not load the Panda embodiment, train the LeRobot policy from <https://github.com/nebius/serverless-ai-cookbook/tree/main/robotics/lerobot-finetune-job> and label the cell with that policy name.

Tonight: do not run this. `usefulness` is `null`.

## Realism

Claim it supports: the twin looks like the room.

Protocol, later: for scan frames that have RGB, depth, and a camera pose, render the twin from that pose and report image error and depth error. Do not invent a metric name until the frames exist. Candidate metrics to compute then, not tonight: mean L1 on depth in meters, and a pixel error on RGB. Mask out the robot if it is not in the scan photo.

Blocked when `blocks_claims` contains `realism` (the four-photo bundle).

Tonight: no scan frames with poses are in the repo. `realism` is `null`.

## What runs today

`python -m arrival eval --policy scripted|vla --families <list|all> --episodes N --seed S --people P [--holdout]` is the harness for the usefulness protocol, sim-in-the-twin only. It runs N episodes per family through the same MuJoCo env and physics success check as `sim`, writes no dataset, and reports per family: success rate with a Wilson 95% interval, mean sim time (frames / 20 Hz), mean wall time, human contacts, the smallest robot-human distance, and the largest IK residual. An episode in which the robot reaches a person is a failure. The split above is enforced in `arrival/sim/tasks.py`: `sim` datasets never contain wording template 4 or the start offset `[0, +0.08]`, and `--holdout` draws only those (`open_drawer` and `open_door` have three wordings and no start pose, so they keep all three either way). The sim applies half the y offset, so the held-out start is +0.04 m in y. The output is `out/eval/<run_id>/report.json`, shape in [04-contracts.md](04-contracts.md).

What it does not do yet: the success rule above (0.05 m of the target point, gripper open) is not what it checks; it uses the physics rule from `collect.py` (object resting inside the target fixture, or the joint past its threshold). Arm-fixture collisions are counted, not scored: an episode where an arm link (link1 to link7; the hand and fingers are meant to touch handles) touches anything but the robot, people or free objects is reported per family as `arm_contact_episodes` with the deepest penetration (`arm_contact_max_depth_m`), and the worst pair is logged. `--policy vla` has only been run far enough to confirm it stops with a message when `GR00T_POLICY_URL` is unset; the three cells need a GR00T server (POL-3) and a fine-tune (DAT-2). With 4 episodes per family the Wilson interval is 0.5 wide; the protocol's 50 per cell brings it to about 0.1.

## Replaying identical trials

The first evaluation freezes its full twin, ordered tasks, seed, people count, holdout split, resolution and fixed-base rollout settings in `out/eval/<run_id>/manifest.json`. Its SHA-256 ID covers the canonical JSON contents. Replaying this file does not compile the room or generate tasks again. A changed hash, inconsistent twin, duplicate task ID or unsupported rollout setting is refused before simulation.

Use `--manifest PATH --policy vla --checkpoint-id LABEL` for each policy server checkpoint. Copy the manifest path printed by the first run. `--manifest` cannot be combined with generation options such as `--room`, `--seed`, `--episodes`, `--people`, `--res` or `--holdout`; these values come from the file. VLA runs require a nonempty checkpoint label. This is a caller declaration, not evidence of which weights the remote server loaded.

Every invocation gets a new run directory, even with the same policy and checkpoint label. `episodes.jsonl` records each completed or failed attempt with its trial index, task ID, physics success, contact-adjusted success, safety measurements, times, error, manifest ID and checkpoint ID. The aggregate report is derived from these rows. Failed or invalid rollouts have unknown simulation time and safety measurements, shown as null. Means and contact counts use only `observed_episodes`; all attempts remain in the success-rate denominator. If the first server request fails, the attempt and manifest remain on disk but there is no completed `report.json`; the cost reader ignores that partial run. Families with no generated tasks are listed as omitted.

The manifest fixes inputs, not outcomes across software versions. Reports record Python, MuJoCo and NumPy versions; comparisons should also use the same source revision and policy settings. This implementation supports the fixed base only. Replay and mock-server tests establish evaluation bookkeeping, not learned-policy usefulness. The three-cell experiment still needs real checkpoints and GPU access.

## What a demo video may say

If a video is cut later, it may show the local page, the schematic frames, and the dataset folder. It must say the motion is a scripted placeholder in simulation. It must not show a physical robot, a splat, or a fine-tuned policy unless those were actually run.
