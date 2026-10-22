# SIM-7a: appearance variation stage

Issue #70 (SIM-7, offline part). Code: `arrival/render/variation.py`, tests: `tests/test_variation.py`.

## Contract

- Input: a finished, validated dataset with mp4s. Output: a new directory (copy); the source is never modified.
- Selection: per episode, the round(fraction x length) frames with the smallest sha256(episode:frame:seed).
- Backends: `cosmos` (POST PNG to `COSMOS_URL`, image back; headers `X-Cosmos-Model`, `X-Cosmos-Version` name the model) and `local_stub` (seeded jitter + blur, geometry fixed).
- Acceptance per frame: edge-map correlation >= 0.6 and, with a mask, normalised masked change <= 0.35. Otherwise `rejected`, frame stays original. Backend errors give `failed`; after 3 consecutive failures the remaining requests are `skipped` (still `failed`, with `skipped: true`).
- Sidecar `meta/arrival_variation.jsonl`: original_id, variant_id, backend, model, version, parameters, latency_ms, status, reason, edge_corr, mask_change.
- Label `arrival_appearance_variation`: `cosmos` only if a cosmos frame was accepted; `local_stub` if only the stub produced frames; else `none`. The summary records backend call time separately from the added stage wall time (copy, calls and video writes). USD stays null without endpoint billing data.

## Not verified

No real Cosmos endpoint has been called; the request/response format is an assumption tested only against a local mock server.
