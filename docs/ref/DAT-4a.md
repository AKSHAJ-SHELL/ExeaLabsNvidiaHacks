# DAT-4a: seed-demo replay retargeting

Command: `python -m arrival.generate.retarget [--room hero_kitchen] [--attempts 6] [--family counter_to_sink] [--res 64] [--seed 0] [--baseline]`

Writes `out/datasets/<room>_seed_replay/` (LeRobot v2, same writer as `sim`), `out/seeds/<seed id>.json` (the recorded seed: waypoints per segment, relative to their anchors) and `out/reports/<room>_seed_replay.json`.

## Method
1. Run the scripted expert on one task and keep its planned eef waypoints (`_Recorder`). The seed must succeed under the physics oracle; otherwise the next candidate task is tried.
2. Label each waypoint with its segment: approach, grasp, lift (anchored to the object's body position), carry, place, release, retreat (anchored to the place point).
3. For each attempt draw a start-pose delta (default +-10 cm x, +-5 cm y) and a place-point shift (+-3 cm), build the env with the moved object and re-anchor every waypoint. IK worst error over 2 cm: dropped as `unreachable`, no rollout.
4. Otherwise roll out with `ReplayPolicy`, check with `SimEnv.success`, and write only successes without human contact.

## Labels (`meta/info.json`)
`arrival_generator = "seed_replay_retarget"`, `arrival_physically_valid = true` (each episode passed the sim oracle), `arrival_seed_episode_id`, `arrival_seed_ref`, `arrival_attempts`, `arrival_successes`, `arrival_dropped`. The strings `mimicgen` and `scripted_retarget` are not used.

## Limits
Translation only (object yaw is not tracked), pick-and-place families only, one seed, rim- and handle-held objects keep the seed's grasp offset. Not MimicGen: no RoboCasa, no Linux requirement, no seed set. Nothing here involves a real robot.

## Measured (hero_kitchen, counter_to_sink, people 0, res 64, 6 attempts)
6/6 exported; start xy std 5.8 cm / 3.6 cm; 979 demos/hour against 1146 for the scripted expert on 6 tasks; 390 MB peak.
