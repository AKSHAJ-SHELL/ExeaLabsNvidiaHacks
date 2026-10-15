# MVP tonight

A reviewer can clone the repo, run one command, and get a GR00T-shaped dataset of the hero kitchen plus a local page that shows that room and queues an upload. Nebius credentials are not required.

## Definition of done

From a clean checkout, these pass:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m arrival demo --episodes 4
python -m arrival validate out/datasets/hero_kitchen
python -m arrival demo --episodes 1000 --videos sparse
python -m arrival validate out/datasets/hero_kitchen
python -m arrival serve
```

`serve` listens on `127.0.0.1:8000`. These URLs work:

- `GET /` lists `hero_kitchen` and shows `geometry_source`, task counts, and dataset path.
- `GET /rooms/hero_kitchen` shows fixtures, the two tasks, and `arrival_physically_valid: false`.
- `GET /download/hero_kitchen` returns a `.zip` of `out/datasets/hero_kitchen`.
- `POST /jobs` with a multipart file field named `scan` returns HTTP 202 and `{"status":"queued",...}`. The process does not compile or generate inside that request.

## Dataset bar

`out/datasets/hero_kitchen/` after the 1,000-episode command:

- `meta/info.json`, `meta/tasks.jsonl`, `meta/episodes.jsonl`, `meta/modality.json`, `meta/embodiment.json`
- 1,000 successful episodes in parquet under `data/chunk-000/`
- At least 8 mp4 files under `videos/chunk-000/observation.images.ego_view/`
- Both task families present
- `info.json` fields: `arrival_generator = "scripted_retarget"`, `arrival_physically_valid = false`, `arrival_successes = 1000`
- `out/reports/hero_kitchen.json` has attempts, successes, wall seconds, demos per hour, and a dollars object whose values are 0 with `"measured": false` except `"local_cpu"`, which is measured as 0 dollars
- The 1,000-episode command finishes in under 15 minutes on a laptop. If video encoding breaks that budget, keep `--videos sparse` as the required path and say so in the README.

## Smoke bar

The 4-episode command writes a dataset the validator accepts, with at least one episode of each task, and finishes in under 60 seconds.

## README bar

Root `README.md` tells a stranger how to install, run the smoke demo, run the 1,000-episode demo, open the page, and where credentials would go. It states that the motion is not physically valid. It links `docs/08-access.md`. It contains a cost table with one row per Nebius product from the spec, filled with "not measured" where no call was made.

## Not done if

- The only dataset is chat JSONL, HDF5, or a custom numpy dump.
- The page blocks on generation.
- Tests need the network.
- The README claims a splat, MimicGen, GR00T training, or a real-robot result.
- `out/` is committed. It is gitignored. The sample scan under `scans/` is committed.
