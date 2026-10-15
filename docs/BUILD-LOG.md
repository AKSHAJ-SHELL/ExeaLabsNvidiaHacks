# Build log

Deviations from the contract, one paragraph each.

**Family interleave in sampling.** The contract says to shuffle the task product with `random.Random(0)` and cycle. With 192 tasks, the first 4 shuffled tasks were all `counter_to_counter`, which fails the smoke bar (each family must be in the 4-episode run). `arrival.tasks.propose.shuffled` still shuffles with `Random(0)`, then interleaves the two families while keeping the shuffled order within each one. The miss pattern still sits on attempt indexes 9, 19, 29, …

**Sidecar path.** The contract's `embodiment.json` example gives `cartesian_sidecar: "../hero_kitchen.cartesian.jsonl"` relative to `meta/`, but it also places the sidecar at `out/datasets/<room>.cartesian.jsonl`, outside the dataset folder. The writer records `../../hero_kitchen.cartesian.jsonl`, the path that actually resolves from `meta/`. A test checks that it resolves.

**Validator exit code.** The contract's validator section says "Exits 0 when a required file is missing or a slice is wrong", which contradicts the exit codes in 05-repo-map.md. The validator exits 1 in those cases.

**`--from-roomplan` objects (superseded, see below).** RoomPlan does not capture small objects, so the RoomPlan bundle has none and no tasks can be proposed from it alone. The first version borrowed the object placements from `scans/<room>/scan.json` when that file existed. The twin is smaller, with only the sink plus a synthesized counter. If the counter inset rejects the scanned pose, the seed falls back to the lowest surviving start pose.

**Timing.** On an Apple Silicon laptop, `demo --episodes 1000 --videos sparse` takes about 1 s for generation and export (1,111 attempts, 111 dropped, 8 mp4s). `--videos all` for 1,000 episodes was not needed and was not timed.

**Real RoomPlan exports.** The first normalizer assumed plain-string categories and a floor at ARKit y = 0. Real exports (2 public ones now in `tests/fixtures/roomplan/`, sources in its README) use keyed enums (`{"chair": {}}`), camelCase (`washerDryer`), a `confidence` enum, a floor around y = -1.5, zero wall thickness, and arbitrary room rotation. `arrival.scan.roomplan` now unwraps enums, snake-cases categories, drops `low` confidence, subtracts the floor height, gives zero-thickness walls 0.1 m, rotates the room so the longest wall runs along +X, moves the wall bounding box to (0, 0), and snaps yaws within 5° of 90° multiples. Tests check that both real exports normalize, compile, rest on the floor, and form closed wall loops.

**Placed objects instead of borrowed ones.** `--from-roomplan` no longer copies objects from the authored scan. `arrival.twin.compile.place_default_objects(twin, seed)` puts a mug and a bowl (catalog sizes) on the counter nearest a sink (synthesized or scanned; dining tables last), rejecting spots over a sink or stove, with `random.Random(seed)`. Objects carry `placed_by: "place_default_objects"`. The proposer now picks the counter that holds objects as the source. Neither public real export contains a kitchen fixture, so they yield 0 tasks; a synthetic kitchen in Apple's encoding (rotated 30°, floor at -1.4) is the test that yields both families.

**Synthesized counter length.** A counter synthesized around a sink or stove is now `max(width + 1.2, 1.8)` m long (was `max(width + 0.4, 1.2)`), so there is room beside the sink to place objects. It inherits the fixture's yaw, with its long axis along the fixture's local X.

**Yaw-aware geometry.** `in_top_rect`, `_rect_distance` and so `on_counter` transform points into the fixture's local frame (`arrival.twin.compile.to_local`). In `layout.yaml`, axis-aligned walls keep their swapped-size convention; oblique walls get `size = [length, thickness, height]` plus `z_rot` from the wall direction.

**`--scans` default.** A relative `--scans` that does not exist in the cwd resolves against the repo root (`arrival.cli.resolve_scans`). A missing room or a missing `roomplan.json` exits with a message naming the path.

**Upload hardening.** `POST /jobs` streams the body to a temp file in 1 MB chunks, then finds the `scan` part by boundary scanning over an mmap (no `email` parser, no full in-memory copy). A body shorter than `Content-Length`, a missing closing boundary, an empty file, or no filename returns 400. The handler has a 30 s socket timeout. The room page links `out/datasets/<room>_sim` when it exists and shows its `arrival_generator`, `arrival_physically_valid`, `total_episodes` and families (`arrival_families` or `families`).

**`.env` for Token Factory.** `arrival.models.token_factory.config()` reads `.env` from the cwd or repo root with a small stdlib parser, only when `TOKEN_FACTORY_API_KEY` is unset, and never overrides set variables. Nothing else loads `.env`.

**Scope change: MuJoCo allowed.** The project lead overrode docs/01-decisions.md: MuJoCo is now an optional `sim` extra and the scope includes simulation with drawers, doors and moving people (`arrival/sim/`, built separately). README documents it and lists the remaining gaps.

- Integrator: sim drawer on counter_a was blocked by the closed cabinet door panel overlapping the drawer stack; door width now shrinks to clear the drawer (`door_w`), open_drawer 8/8. Cabinet door hinge axis flipped so it swings outward (it previously rotated into the carcass); open_door is still 0% (IK/reach), not claimed.
