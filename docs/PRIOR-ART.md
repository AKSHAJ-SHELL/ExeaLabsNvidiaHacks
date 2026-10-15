# Prior art

WALK·IN Arrival is a new pipeline written in this repo during the hackathon. It builds on ideas from an earlier project by the same team, [Walk-In](https://github.com/AvnehSBhatia/Walk-In). No Walk-In code is imported or vendored here, and the Arrival demo does not call World Labs Marble.

## Already existed before this hackathon (in Walk-In)

These were built before the hackathon, in <https://github.com/AvnehSBhatia/Walk-In>:

- Four-photo room capture.
- Marble (World Labs) reconstruction of the room from those photos.
- A MuJoCo room built from the reconstruction.
- Spot and humanoid robot rigs.
- A skill-level pick that attaches the object to the hand. It is not contact physics.
- A scripted oracle that judges attempts.
- Chat-style JSONL output, with failed attempts relabeled as text.

## Built in this repo for Arrival

- RoomPlan normalization: Apple RoomPlan `CapturedRoom` JSON goes to a ScanBundle, converting ARKit Y-up to Z-up (`arrival/scan/`).
- A RoboCasa-subset layout compiler that turns the ScanBundle into `twin.json` and `layout.yaml`, including the fixture category map and counter synthesis (`arrival/twin/`, `arrival/catalog/`).
- Task variations for two families (`counter_to_sink`, `counter_to_counter`) across object, start pose, lighting, and instruction wording (`arrival/tasks/`).
- Scripted retargeting of seed trajectories, plus a distance oracle that drops misses, exported as a GR00T LeRobot v2 dataset with `meta/modality.json` and `meta/embodiment.json` (`arrival/generate/`, `arrival/export/`).
- 64×64 `sim_texture` schematic frames (`arrival/render/`).
- A local page for pre-scanned rooms, a dataset zip download, and a queued upload endpoint (`arrival/web/`, `arrival/jobs/`).

## Carried over as ideas only

- The four-photo input slot. In Arrival it produces a bundle flagged `four_photo_unmeasured`, which blocks geometry and realism claims.
- An oracle that drops failed attempts. Arrival drops them instead of relabeling them into chat JSONL.

## Not claimed

Arrival tonight does not run MimicGen or contact physics. It does not train a Gaussian splat or GR00T, and it has no real-robot result. See [09-later.md](09-later.md).
