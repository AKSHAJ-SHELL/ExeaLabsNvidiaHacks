# Arrival — start here

> This is the original one-night MVP contract. The branch has moved past it: MuJoCo simulation, the upload worker, the iOS capture app and Tavily research all exist now (see the [README](../README.md) and [REFERENCE.md](REFERENCE.md)). Where this file and the README disagree, the README wins. The honest-label rules below still hold for the `demo` dataset.

You are the implementing agent. The product spec is `plan.pdf` at the repo root. This `docs/` suite is the build contract. It is already decided. Do not re-plan, do not ask the user to pick an architecture, and do not wait on Nebius, GR00T, or a real iPhone scan.

Paste this to yourself and start at task T01 in [06-agent-tasks.md](06-agent-tasks.md):

> Build the Arrival MVP described in `docs/`. Follow `docs/06-agent-tasks.md` in order. `docs/01-decisions.md` wins over every other doc. `docs/06-agent-tasks.md` wins over the reference docs. Stop when `docs/02-mvp-tonight.md` definition of done passes. Do not implement items in `docs/09-later.md`.

## Read order

1. [01-decisions.md](01-decisions.md) — locked choices. Do not reopen them.
2. [02-mvp-tonight.md](02-mvp-tonight.md) — what "done" means.
3. [06-agent-tasks.md](06-agent-tasks.md) — do these in order.
4. [04-contracts.md](04-contracts.md) — schemas. Copy them. Do not invent parallel ones.
5. [03-architecture.md](03-architecture.md), [05-repo-map.md](05-repo-map.md), [07-eval.md](07-eval.md) — reference while you implement the matching task.
6. [08-access.md](08-access.md) — links for the human. You do not block on them.
7. [09-later.md](09-later.md) — do not build these tonight.
8. [10-risks.md](10-risks.md) — fallbacks already chosen.

## What this repo is

Arrival turns one room scan into robot demonstrations in that room. Tonight's code is a new pipeline in this repo. Do not call World Labs Marble.

## Honest label

The dataset written tonight is a real GR00T LeRobot v2 folder. The motion inside it is a scripted placeholder, not MimicGen and not contact physics. `info.json` must say `"arrival_physically_valid": false`. The README must say not to fine-tune GR00T on it until that flag is true.
