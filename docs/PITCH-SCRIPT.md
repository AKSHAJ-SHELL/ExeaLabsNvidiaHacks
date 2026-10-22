# Pitch video script (about 2:30, under the 3-minute Devpost limit)

Record a screen capture plus voiceover. Speak at about 150 words a minute; the narration below is about 370 words. Items in [brackets] are for you to fill in or confirm before recording. Do not say anything the repo marks as not done.

## What to have open
- https://arrival.exealabs.org (the demo page)
- `docs/media/demo.mp4` (the 30-second sim render)
- `docs/media/ego-exo.png` (robot, wrist and room views)
- A terminal at the repo root, ready to run `make demo`
- The model card: https://huggingface.co/Ish1105/arrival-gr00t-n17-run4

## Script

**0:00 to 0:15. The problem** (screen: title card, then a still of a kitchen)
"Robot arms are trained in generic simulated kitchens. Your kitchen is different. Arrival turns a scan of a real room into a simulated copy of it, and into training data for NVIDIA's GR00T."

**0:15 to 0:45. Scan to twin** (screen: demo page, scan stage, then twin stage; drag the scan/twin divider)
"You scan the room with a LiDAR iPhone. Arrival reads the walls, cabinets, drawers, fridge and doors, and builds a physics twin in MuJoCo. We ran a real kitchen, scanned on an iPhone 13 Pro Max, through the whole pipeline. It broke on the first try, because objects faced the wrong way. We found it, fixed it, and kept that scan as a regression test."

**0:45 to 1:15. Sim to dataset** (screen: demo.mp4, then terminal running `make demo`)
"In the twin, a scripted arm opens drawers, doors and the fridge, puts a mug away, and wipes the counter, while people walk through and the robot yields. A reach check rejects tasks the arm can't do from where it stands. Every episode is checked, then exported as a LeRobot dataset, with robot, wrist and room cameras."

**1:15 to 1:55. The GR00T result** (screen: model card results table)
"We fine-tuned GR00T N1.7 on one room's data. The clean-data model succeeded in 26 of 48 trials. Adding DART demos with injected noise made it worse, 22 of 48, because the noisy drawer pulls were bad data. Filtering out 102 marginal pulls gave 39 of 48, 81 percent, with a paired sign test p of 0.007."
"Honest limits: this is simulation only, one room, two tasks, one seed, and one run per model."

**1:55 to 2:20. How to run it and where it runs** (screen: README top, then terminal)
"Everything is open source under Apache 2.0. `make install`, `make test`, `make demo`. Jobs run through a web app with workers, shards that resume after a crash, and a Nebius fan-out backend. [Say what actually ran on Nebius: the fine-tune host, or a Token Factory call. If nothing did, leave this out.]"

**2:20 to 2:30. Close** (screen: repo URL and demo URL)
"Arrival. Scan your kitchen, get a robot-ready dataset. The code, the checkpoint and the evidence are all linked from the repo."

## Do not say
- That we scanned three kitchens. One real kitchen went through the pipeline; the three-scan set (P2) is not done.
- That it runs on a real robot. It does not.
- That it beats base GR00T or generic RoboCasa. Those comparisons were not run.
- Anything about Nebius you can't back up with a run.

## Recording checklist
- Record at 1080p, a quiet room, and a headset mic. Keep the voice flat and unhurried; cut and re-record lines, don't try one take.
- Keep the final cut under 3:00. Judges are not required to watch past 3 minutes.
- No copyrighted music. Upload as public on YouTube, then add the link to the README and flip P4 to done in `site/data/todo.json`.
