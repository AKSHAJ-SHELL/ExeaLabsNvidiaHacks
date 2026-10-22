# Contributors

Who worked on what. Pull request authors come from GitHub; the commit counts are `git shortlog -sn` on this branch. Merges keep each commit's original author, so the git history credits the same people. Regenerate with `python scripts/render_contributors.py`.

Work on this repository's laptop pass was done by the repo owner with Claude Code agents. Those commits end with a `Co-Authored-By: Claude` line.

## Commits by author

```
   227	redmythic1
    60	aarochu
    39	Aadi Tiwari
    13	Jahan Marbin
    12	IshaanM05
     9	Avneh Singh Bhatia
     5	Akshaj Shandilya
     3	Anand Biju
     2	Amelia Patel
     2	amanx98
     1	rishithc
```

## From forks, with no pull request

- **@rishith-c**: Synchronized ego, wrist and exocentric capture, side-by-side preview, optional three-camera GR00T config (`rishith-c/ExeaLabsNvidiaHacks:feat/ego-exocentric-capture`)

## Pull requests by author

### @aarochu (56)

- #44 CAP-4: Add field scanning protocol (merged)
- #45 DEM-3: Refresh release status and setup guidance (closed)
- #46 TWN: Avoid duplicate counters over scanned base cabinets (closed)
- #47 [MAN-2] Door and drawer collision boxes match their visible fronts, so the arm can't pass through them (merged)
- #48 DEM-2: Refresh the demo video from the current scene (closed)
- #49 TWN: Avoid duplicate counters over scanned base cabinets (merged)
- #50 DEM-2: Refresh the demo video from the current scene (merged)
- #51 [OPS-1] Write job status.json atomically so polling never reads a half-written file (merged)
- #52 Validator: reject NaN/inf state and action, and timestamps that don't match the fps (merged)
- #118 Guard public uploaded job assets by owner (merged)
- #126 Match hosted retention notice to worker policy (merged)
- #128 Validate fan-out run IDs before writing shard paths (merged)
- #129 Reject invalid fan-out scheduling controls (merged)
- #130 Reject non-finite cost and usage inputs (merged)
- #131 Fail clearly on unknown fanout job states (merged)
- #132 Match teleop comparisons to reported tasks (merged)
- #133 Validate appearance variation sampling inputs (merged)
- #134 Reject malformed appearance variation frames (merged)
- #135 Reject fractional count limits in worker configuration (merged)
- #136 Validate realism camera transforms before scoring (merged)
- #137 Validate fanout done markers before resuming (merged)
- #138 Keep RGB-D frame files inside their bundle (merged)
- #139 Require RGB-D split lists to match frame labels (merged)
- #140 Exclude invalid success counts from cost throughput (merged)
- #141 Validate frozen evaluation trial fields (merged)
- #142 Verify shard episodes belong to their declared range (merged)
- #143 Fetch only the expected fanout shard result (merged)
- #145 Reject malformed Cosmos image responses (merged)
- #147 Keep original videos when a variation mask is invalid (merged)
- #148 Match resumed journal records to task order (merged)
- #149 Require scoped usage for task cost comparisons (merged)
- #166 Reject unchanged appearance variation frames (open)
- #167 Prevent variation output inside its source dataset (open)
- #168 Match custom variation clients to requested backends (open)
- #169 Report committed usage ledger corruption (open)
- #170 Validate worker metering before reporting totals (open)
- #171 Preserve corrupt committed journal lines for diagnosis (open)
- #172 Require stored shard artifacts before marking completion (open)
- #173 Validate fanout simulation settings at construction (open)
- #174 Reject confidence images with mismatched depth size (open)
- #175 Validate ARKit confidence image levels on upload (open)
- #176 Check shard episode files before replacing merge output (open)
- #177 Report corrupt shard metadata before merge (open)
- #178 Refuse fanout resume on corrupt run manifests (open)
- #179 Validate appearance variation geometry thresholds (open)
- #180 Handle malformed appearance backend responses (open)
- #181 Validate frame rate before appearance variation copy (open)
- #182 Validate realism scoring controls before reading scans (open)
- #183 Require float32 metric depth in uploaded frames (open)
- #184 Require color channels in uploaded RGB frames (open)
- #185 Reject boolean dimensions in RGB-D manifests (open)
- #186 Add GR00T fine-tune preflight for existing configs (open)
- #187 Reject mismatched mobile policy action chunks (open)
- #188 Implement depth compositor for static and moving RGB-D layers (open)
- #189 Fix scan intake handoff to the 5 cm accuracy gate (open)
- #190 Measure appearance variation stage and backend latency (open)

### @Aadi-Tiwari (32)

- #4 [MAN-2] Open doors: tilted grasp, clearance path, via-point pull (merged)
- #5 [TWN-6] Sample kitchen: fridge, counters and stove tile the wall without overlap (merged)
- #10 [TWN-2][TWN-3] Scan regression suite and full RoomPlan coverage (merged)
- #11 [MAN-5][MAN-4] Four new task families and a bowl the gripper can hold (merged)
- #12 [OPS-1] Upload worker: queued scan -> twin -> sim dataset -> downloadable zip (merged)
- #13 [POL-4][PPL-2] Closed-loop eval harness, people interactions, human-contact safety metric and a real held-out split (merged)
- #19 [SIM-3][SIM-4] Oven, dishwasher, microwave and wall-cabinet doors, a faucet lever, and nine objects with real mass and size variation (merged)
- #21 [SIM-2] Key, fill and window lights with per-episode variation, and tile, wood and stone materials (merged)
- #23 [PPL-1] Proportioned walking people with a gait, seeded heights and colours, and paths that keep clear of the fixtures (merged)
- #25 [MAN-6] Real Franka Panda from MuJoCo Menagerie behind --arm menagerie, tests stay offline (closed)
- #27 [MAN-5] Open the oven and dishwasher, turn on the faucet, load and unload the dishwasher (closed)
- #29 [DEM-3] Release QA on a fresh clone of main, stale README and doc claims fixed, checklist added (merged)
- #31 [MAN-4] Plates by the rim and pans by the handle, so every catalog object but the spatula is picked (merged)
- #33 [MAN-3] Mobile base behind --base mobile: base pose in the state and action, counter_to_counter reachable (closed)
- #71 [MAN-1] Wrist camera frames what the gripper holds, joint 7 stays off its +2.90 stop, and every episode's video renders on Windows (merged)
- #73 [PPL-2] A person opens the fridge: hand on the bar, kinematic hinge, doorway stop, door contact counts as human contact (merged)
- #75 [SIM] Fixtures on any wall: base parks along each fixture's own front, walkers get the strip in front of that run (fixes #42) (merged)
- #76 [PPL-1] Walkers slow into a stop, so the swinging foot no longer enters the counter (merged)
- #77 [SIM] Scanned kitchens get tasks on their cabinets, and every scanned fixture is solid (refs #42) (merged)
- #78 [MAN-5] The arm opens the fridge: pull by the bar to 40 deg, push the inside face to 80 deg, 32/32 with and without people (merged)
- #108 [DEM-3] Fix Windows checks and require a separate rendering gate (open)
- #109 [DAT-3] Replay frozen trials and keep each evaluation run (merged)
- #110 [EVAL-1a] Connect uploaded frames to worker comparison results (open)
- #116 [L17] Reachability planner: IK pre-flight on the expert's waypoints, fallback base spots when the stand rule's spot cannot reach (open)
- #117 [L26] The spatula is pinched, picked into the sink and used to wipe the counter (open)
- #119 [L27] People give way to the arm, work the counter, and open a left-hinged fridge (open)
- #127 [P3] Record twenty timed human teleoperation demos (merged)
- #157 [C4] Detect small objects from posed RGB-D frames and place them in the twin (offline slice) (open)
- #158 [L27] A fridge can hang on its right; let go of the bar before sliding off it (open)
- #159 [G1] Stand open_oven to the side of the bar, open_door further out when hinged by a wall (open)
- #160 [C1] Nebius backend for the fan-out: Serverless AI Jobs plus Object Storage, tested against fakes (open)
- #191 [G1] close_door: stand nearer the hinge where the run ends flush against a wall (open)

### @AvnehSBhatia (30)

- #1 Add tonight's MVP handoff (merged)
- #80 Integrate 16 open PRs, 40+ bug fixes, new web page, refreshed README (merged)
- #81 [DOCS] Before the deadline: blocked items, laptop sprint, known bugs (merged)
- #82 [INF-1] CI workflow, Makefile and CPU Dockerfile (merged)
- #83 [POL-3] GR00T policy-server contract: offline mock server, shim and VLAClient fix (merged)
- #84 [DAT-2a] Offline GR00T/LeRobot loader conformance check (merged)
- #85 [OPS-3a] Time and cost report from local runs, no unsupported savings claim (merged)
- #86 [DEM-4] One-command demo pipeline with summary (merged)
- #87 [CAP-3a] Scan intake tool: privacy strip, notes, checks and render (merged)
- #88 [EVAL-1a] Realism metrics: render twin from a camera pose and score RGB and depth error (merged)
- #89 [DAT-4a] Seed-demo replay retargeting in the sim (seed_replay_retarget) (merged)
- #90 [CAP-2a] RGB-D scan-frame manifest, loader, validator and unprojection (merged)
- #91 [DEM-3a] Docs and README claim checker (merged)
- #92 [TWN-1a] Scan accuracy harness: twin dimensions vs tape measurements (merged)
- #93 [SIM-7a] Appearance-variation stage with source tracking and honest labels (merged)
- #94 Sprint PRs #82-#93 combined, conflicts resolved (merged)
- #95 [DOCS] Code to-do before submission (merged)
- #96 Worker limits, concurrent claiming, retention and usage metering (L3, L18, L19, L20) (merged)
- #97 Web hardening, arrival doctor, RGB-D frames upload (L4, L22, L14) (merged)
- #98 W3: CI matrix, repo checks and an offline make demo (L6, L7, L8, L21) (merged)
- #99 SIM: fixtures on any wall, reach pre-flight, skip instead of crash (#42; includes #49, #75, #77) (merged)
- #100 W4: twin compile fixes, scan fuzz, provenance, arrival realism (L10, L11, L15, L16) (merged)
- #101 Ignore site/ (demo site is deployed to Vercel separately) (open)
- #102 Per-episode validator, multi-room summary, static page export (L12, L28, L23) (merged)
- #103 L13: mobile base (#33) on any-wall, 11-float schema through export, GR00T config and loader check (merged)
- #104 L5: shardable, resumable sim collection (--shard, --resume, merge-shards) (merged)
- #105 L9: non-kitchen rooms (takes over #57) with room-appropriate objects (book, remote, laptop) (merged)
- #106 [L24] Oven, dishwasher and faucet families (#27) rebased onto the any-wall chain (merged)
- #107 L25: real Menagerie Franka behind --arm menagerie (rebases #25) (merged)
- #164 Gap fixes (door joints, fridge hinge, corner door, Menagerie) + teammate PRs #118, #126-#150, #152-#155 (merged)

### @JmarbinGG (8)

- #43 [CAP-1] iOS RoomPlan capture app: scan, share, upload to /jobs (merged)
- #113 [L20] Timed keyboard teleop baseline for the cost comparison (merged)
- #114 [L22] Single config loader, .env.example and secret redaction (merged)
- #115 [C2] smoke_hosted.py: good and bad upload check for a running server (merged)
- #144 Hand checks: fix browser upload with an empty frames input; delete the sim journal with a job (merged)
- #146 [G1] Write q01/q99 into stats.json for GR00T percentile normalisation (merged)
- #150 [CAP-2] Record RGB-D frames in the iOS app during a RoomPlan scan (merged)
- #151 close_door: push the panel above the bar (G1 joint_at_limit 5 -> 3); re-measure open_door (open)

### @AKSHAJ-SHELL (6)

- #53 [MAN-2] Cabinet fronts collide where they are drawn; arm clipping test (closed)
- #55 [POL-4] Count arm-fixture contacts in eval (merged)
- #57 [SIM-5] A scanned office becomes a room the arm can work in (merged)
- #156 [P2] Three consented real kitchen scans with tape measurements; licence check of the public scans (open)
- #163 CI: mark the three tests that render in a child process as render (main's portable jobs are red) (open)
- #192 Job memory cap on Linux: measured (RLIMIT_AS crashes jobs and follows core count); resident-memory limit in the worker (open)

### @IshaanM05 (6)

- #9 DEM-3: pin video writer to the FFMPEG backend (merged)
- #38 DAT-1: GR00T N1.7 modality config for the sim Panda (merged)
- #155 POL-3: gr00t_shim run against real GR00T, plus GPU run notes (merged)
- #161 POL-3: gr00t_shim serialises concurrent requests, plus optional sample averaging (open)
- #162 SIM: sim --dart, drive the arm off the plan while the dataset keeps the clean targets (open)
- #165 DAT: record the GR00T fine-tune results and what they showed (G1, DAT-2) (open)

### @app/dependabot (6)

- #120 build(deps): bump nvidia/cuda from 12.8.0-cudnn-devel-ubuntu22.04 to 13.4.3-cudnn-devel-ubuntu22.04 (open)
- #121 build(deps): bump actions/setup-python from 5 to 7 (open)
- #122 build(deps): bump python from 3.11-slim to 3.13-slim (open)
- #123 build(deps): bump actions/checkout from 4 to 7 (open)
- #124 build(deps): bump actions/upload-artifact from 4 to 7 (open)
- #125 build(deps-dev): bump ruff from 0.11.13 to 0.17.1 (open)

### @Anandb71 (3)

- #152 close_door, open_oven: keep every arm joint off its stops (merged)
- #153 [TWN-3] Draw RoomPlan doors, windows and openings in the sim as visual-only geoms (merged)
- #154 [OPS-1] Upload worker: retry a failed job a bounded number of times (merged)

### @amanx98 (3)

- #3 feat(policy): [POL-1] [POL-2] Wire Nemotron VLMPlanner into sim colle… (merged)
- #35 feat(research): [TAV-1] Implement Tavily AI Research Agent for appliance manuals and safety specs (merged)
- #36 [MAN-3] Mobile Manipulator Base & 100% Physics-Checked Counter-to-Counter Transit     (closed)

### @wwpatel (1)

- #2 SIM-1, MAN-1: kitchen and Panda arm visuals (merged)
