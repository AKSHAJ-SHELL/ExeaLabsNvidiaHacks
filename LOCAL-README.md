# What is left, as of 2026-10-21

`main` is at #194, which merged the previous `feat/more-prs-2`. This branch is 9 commits ahead of that: #193 (narrower open-door stand), #195 (demo-page clicks), #196 (site data re-export), #197 (already inside #195), and #198 (parallel rendering in CI). The to-do list is `site/data/todo.json`; run `python scripts/render_todo_readme.py` after editing it, and the README and the demo site both follow.

Setup note: this machine has a stray `tests` package in `~/miniconda3/lib/python3.13/site-packages`. Use a venv (`python -m venv .venv && .venv/bin/pip install -e ".[dev,sim]"`) before running the suite.

Submission fields are from the [hackathon page](https://nebiusglobalaihackathon.devpost.com/) and the [official rules](https://nebiusglobalaihackathon.devpost.com/rules). Deadline: Friday, October 30, 2026, 10:00am Pacific. The cloud rows (C1 to C5) are the Nebius side of that form.

## 1. Land it (needs you)

1. Open a pull request from `feat/more-prs-2` and merge it. #194 already put the previous integration on `main`. Until this branch lands, L32 and L33 stay in review.
2. Close the superseded PRs #25, #27, #33, #36, #49, #57, #75, #77. Decide on #101 (it ignores `site/`, which the branch tracks).
3. Close the stale issues #18, #22, #24, #26, #28, #30, #32, #34 (OWN).

## 2. Check by hand

Run on Oct 21 (#144): fresh clone, two workers, shard/kill/resume and the job buttons all pass; the run found and fixed a broken browser upload and a leftover progress journal. Docker was not run (not installed on that machine).

| Check | How | Where it stands |
|---|---|---|
| Fresh clone on a clean venv | `make install && make test`, then `make demo` in under 5 minutes | Passed on `main` in #144 |
| Two workers on one queue | `arrival serve`, two `arrival work`, upload the hero scan twice | Passed in #144 |
| Shard, kill, resume | `arrival sim --shard 0/2`, interrupt, `--resume`, `merge-shards`, `validate` | Passed in #144 |
| The demo site in a browser | `make site`, open http://localhost:8765, desktop and phone width | Done in #195 at 1024 px and 375 px, both themes. On this branch, not on `main` |
| The job page buttons | upload, then Cancel and Delete (L30) | Passed in headless Chromium in #144 |
| Docker | `docker compose up --build`, then `python scripts/smoke_hosted.py http://127.0.0.1:8000 --wait 600 --require-healthz` | Not run here |

## 3. Known gaps from the laptop work

Re-checked on `main` at c333ee1 (Oct 21):

- Doors: `eval --families open_door,close_door --episodes 8 --people 2` at seeds 0 and 5 gives open_door 16/16 and close_door 16/16, no human contact. open_door has no arm contact (the `counter_b` east-wall graze is gone). close_door on `counter_a` still touches its own door panel with link4 (24 steps, 2.5 mm deep).
- Joint limits: the G1 run (`sim --families all --episodes 28 --people 1 --seed 5`) has 0 of 28 episodes flagged by `validate --episodes` since #152.
- The right-hinged fridge, the Linux memory-cap measurement (#192) and the `site/data` re-export are done. The re-export's exporter fix is #196, on this branch and not on `main`.
- #193, also only on this branch, narrows the open-door stand: 0.12 m further out only when the hinge end is drawn at least 5 mm into a wall and the bar ends the pull within 0.06 m of it, and only when that spot still passes the stand check. The broader "hinge within 0.15 m" trigger is what `main` has.

## 4. Still blocked

GPU: G2 real server, G3 three-cell eval, G4 generic-RoboCasa baseline, G5 scripts never run on a GPU, G6 real RoboCasa load, G7 MimicGen, G8 splat composite. G1 is shipped: 39 of 48 against 26 of 48, small samples, no base-GR00T or generic-RoboCasa cell.

Cloud (C): C1 a real Nebius run, C2 the static-site deploy, C3 measured cost, C4 a real detection call, C5 Cosmos. The rules count the project as running on Nebius only with a Token Factory inference call or a Nebius AI Cloud job, endpoint, or DevPod. Neither has happened (C1).

People: P1 iOS field test, P2 three consented real scans (draft #156), P4 the YouTube pitch. P3's twenty teleop demos are shipped.

## 5. Submission

### Demo video (P4)

`site/motion/pitch.mp4` is the submission video: 24.4 seconds, rendered, no studio recording and no copyrighted music. The closing sheet states the fine-tune as 39 of 48 against 26 of 48, small samples, and leaves real kitchen scans as not done. `docs/media/demo.mp4` is still the silent 31-second code render.

Devpost wants that file as a public YouTube link, under 3 minutes. Judges are not required to watch past 3 minutes. Physical AI has no robot here, so the video shows the modules (scan, twin, sim, dataset, status) instead of hardware. Uploading it to YouTube is the remaining form step (SUB).

### The site (C2)

#195 looked at `make site` / http://localhost:8765 in a real browser, at 1024 px and 375 px, both themes, and fixed the stage buttons, the scan/twin divider, and the phone disclaimer. That check is on this branch, not on `main`. Nothing is deployed.

Deploy with `cd site && vercel --prod`. Put the live URL in the README and on the form if you submit one. The Physical AI track does not require a demo URL.

### The form (SUB)

On https://nebiusglobalaihackathon.devpost.com/, due Friday, October 30, 2026, 10:00am Pacific:

- Track: Physical AI.
- A text description of what it is, why, and how it works.
- The public GitHub URL. The About section has to show the Apache 2.0 license. The README needs setup instructions and has to say where GR00T, Nemotron, Token Factory, and any other Nebius service are used.
- The YouTube link (P4).
- Written feedback on Token Factory, AI Cloud, and the NVIDIA models.
- A demo URL only if you want one (C2). Not required for this track.
- If the project existed before August 26, 2026, a written note of what changed during the submission period.

The project has to run as the video and the text describe, and it still needs a real Token Factory call or a Nebius AI Cloud run (C1) to meet the "runs on Nebius" rule.

Anything that needs real data reports "not measured". Nothing counts as done until its pull request is merged on `main`.
