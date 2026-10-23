# Devpost feedback draft: Token Factory, AI Cloud and the NVIDIA models

Paste the three sections into the Devpost feedback field. The NVIDIA section is from runs we did. The Nebius sections have two parts: what we saw writing the code, and lines marked **[after the real call]** that must be filled in with what actually happened. Delete any bracketed line you can't back with a run.

## NVIDIA models

**GR00T N1.7-3B (fine-tune).** We fine-tuned it on a simulated kitchen built from a LiDAR room scan: a 7-joint arm with a gripper, two camera views, an 8-number state and a text instruction, written as a LeRobot v2 dataset. The checkpoint is at https://huggingface.co/Ish1105/arrival-gr00t-n17-run4.
- What worked: a modality config plus the LeRobot v2 format was enough to load our data. A 100-step smoke run took 58 seconds, and a full run (4,000 steps at batch 32, visual tuning on) took about 51 minutes on one 96 GB GPU. Clean-data fine-tuning scored 26 of 48 in our sim.
- What hurt: we had to pin an Isaac-GR00T commit (`dac54b3`) to get a working setup. The 3B model is about 12 GB in F32, and inference needs 16 GB or more of GPU memory. It was easy to score on the training GPU by accident, and that gave misleading numbers, so we now use one policy server per client and paired trials.
- What we learned: open-loop error on expert frames was 0.3 cm at the next step, but closed loop the gripper closed 2 to 8 cm from the mug, so the failure was compounding drift, not perception. DART-style noisy demos helped grasping but taught the policy to under-pull drawers until we filtered out 102 marginal pulls (39 of 48, against 22 of 48 unfiltered).
- Wish: a documented, versioned recipe for a new embodiment (state and action layout, normalisation, camera names), and a published example of a closed-loop sim evaluation.
- Limits of our claim: simulation only, one room, two tasks, one seed, one run per model.

**Cosmos-Reason2 (the GR00T backbone) and Cosmos.** [Say what you actually used. We ran the fine-tune on GR00T's Cosmos-Reason2 backbone and have an appearance-variation stage with a local stub only. If you did not call a Cosmos endpoint, say so.]

**Nemotron.** The planner client (`arrival/models/token_factory.py`) and the VLM planner in sim collection are written against Nemotron models through Token Factory and tested against an offline cache fixture. **[after the real call]** Which Nemotron model you called, the latency, and whether the output followed the JSON format we ask for.

## Nebius Token Factory

- Seen from the code: the OpenAI-compatible endpoint made the client small (the standard SDK shape, a base URL and a key). We keep model names in environment variables because we could not tell which were available to us without a key.
- **[after the real call]** Sign-up to first response time, rate limits you hit, model availability, error messages, and the price per call. Say if anything in the docs was wrong or missing.

## Nebius AI Cloud

- Seen from the code: we wrote a Serverless AI Jobs backend for sharded simulation with an Object Storage bucket (`arrival/jobs/nebius.py`, `arrival fanout --backend nebius`). It has only run against in-process fakes. The shard design (resume markers, retry) was the harder part; mapping it onto jobs was the easy part.
- **[after the real call]** Did the job start, how long from submit to running, what the logs and status gave you, what the job cost, and what you would change.
- Do not say it ran on Nebius unless the real call happened. The fine-tune did not run on Nebius.
