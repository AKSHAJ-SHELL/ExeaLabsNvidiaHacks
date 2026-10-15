# Risks and chosen fallbacks

Use the fallback. Do not stop to redesign.

| Risk | What you do |
|---|---|
| RoboCasa or MuJoCo will not install tonight | Do not install them. `mimicgen.py` returns skipped. Scripted retarget is the generator. |
| `imageio-ffmpeg` cannot write H264 | Write PNG frames beside the dataset and a one-line `ffmpeg` command in `BUILD-LOG.md`. Validator accepts PNG only if `info.json` says `arrival_video_codec = "png"`. Prefer mp4. |
| 1,000 mp4s are too slow | `--videos sparse` is the required path. Do not drop the parquet episodes. |
| RoomPlan JSON from a real phone does not match the subset | Keep the authored sample as the demo. Put the real file aside. Extend the normalizer only for keys you have in hand. |
| Splat and simulator disagree | Not tonight. Later: texture meshes from photos. See [09-later.md](09-later.md). |
| Scan-to-RoboCasa mapping is messy | Absolute `pos` and `size` in one `main_group`. Unknown categories become `box`. |
| GR00T download is gated or rejects Panda | Do not train. Leave the README command unrun. Fallback later is the LeRobot cookbook policy. |
| Someone fine-tunes the placeholder | `embodiment.json` and the README forbid it while `joints_are_placeholder` is true. |
| Token Factory model ids 404 | Demo does not call it. Client raises `TokenFactoryNotConfigured` without a key. |
| Upload is mistaken for a live pipeline | HTTP 202 and status `queued`. No compile inside POST. |
| Four-photo path blocks the LiDAR demo | Separate function. `demo` loads `scan.json`. |
| Usefulness gain is inside run noise | Later rule: report no gain inside 5–6 absolute points. Speed and cost can still be reported. |
| Serverless preemption | Later: checkpoint to Object Storage and resume. Tonight everything is local under `out/`. |
| Dataset folder is committed | `out/` is gitignored. T14 checks `git status`. |

## Spec contradictions, already resolved

- "Before and after in the scanned room" means the twin, labeled as simulation.
- "Upload a scan, download a dataset" means a queued job plus a download of a precomputed dataset.
- "Grasps and drawers must really open" is the product bar. Tonight's motion does not meet it, and the files say so. Drawers stay later.
- "Thousands of demonstrations" is the product scale. Tonight's generator target is 1,000 successes of placeholder motion.
- Skills that attach the object to the hand are the problem the spec names, not an implementation to extend.
