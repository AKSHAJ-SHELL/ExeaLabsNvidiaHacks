# Build log

Deviations from the contract, one paragraph each.

**Family interleave in sampling.** The contract says to shuffle the task product with `random.Random(0)` and cycle. With 192 tasks, the first 4 shuffled tasks were all `counter_to_counter`, which fails the smoke bar (each family must be in the 4-episode run). `arrival.tasks.propose.shuffled` still shuffles with `Random(0)`, then interleaves the two families while keeping the shuffled order within each one. The miss pattern still sits on attempt indexes 9, 19, 29, …

**Sidecar path.** The contract's `embodiment.json` example gives `cartesian_sidecar: "../hero_kitchen.cartesian.jsonl"` relative to `meta/`, but it also places the sidecar at `out/datasets/<room>.cartesian.jsonl`, outside the dataset folder. The writer records `../../hero_kitchen.cartesian.jsonl`, the path that actually resolves from `meta/`. A test checks that it resolves.

**Validator exit code.** The contract's validator section says "Exits 0 when a required file is missing or a slice is wrong", which contradicts the exit codes in 05-repo-map.md. The validator exits 1 in those cases.

**`--from-roomplan` objects.** RoomPlan does not capture small objects, so the RoomPlan bundle has none and no tasks can be proposed from it alone. With `--from-roomplan`, the CLI borrows the object placements from `scans/<room>/scan.json` when that file exists. The twin is smaller, with only the sink plus a synthesized counter. If the counter inset rejects the scanned pose, the seed falls back to the lowest surviving start pose.

**Timing.** On an Apple Silicon laptop, `demo --episodes 1000 --videos sparse` takes about 1 s for generation and export (1,111 attempts, 111 dropped, 8 mp4s). `--videos all` for 1,000 episodes was not needed and was not timed.
