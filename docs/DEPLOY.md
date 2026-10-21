# Hosting the upload demo

One machine, two containers, a TLS proxy in front. This is the C2 recipe; nothing here has been run on a real host yet, so treat the first deploy as the test.

## Run it

```bash
docker compose up --build -d
python scripts/smoke_hosted.py http://127.0.0.1:8000 --wait 600 --require-healthz
```

`web` serves the page and the upload API with `--public` (a visitor sees only their own jobs, server paths are hidden) and `--behind-proxy` (it trusts `X-Forwarded-Proto` and `X-Forwarded-For`). `worker` drains the queue and, by default, deletes finished jobs after 24 hours. Both share the `arrival-out` volume, so uploads, jobs and datasets survive a restart.

Both containers read the same `ARRIVAL_RETENTION_HOURS` setting, so the page states the worker's actual deletion window. It defaults to 24 hours; set `ARRIVAL_RETENTION_HOURS=0` to keep finished jobs until the uploader deletes them.

## Before it faces the internet

1. Put a TLS proxy in front of `127.0.0.1:8000` and set no other port open. Never run `--behind-proxy` with the port reachable directly: a client could forge the forwarded headers.
2. Keep the limits in `docker-compose.yml`: 50 MB uploads, 10 uploads per minute per client, 20 queued jobs, 900 s per job, 20 episodes and 2 people per job. They are the only protection against a visitor filling the disk or the CPU.
3. Run `scripts/smoke_hosted.py https://your-host --wait 600 --require-healthz` from another machine. It uploads one real job and checks that bad uploads and crafted paths are refused.
4. Do not put API keys in the image. `arrival doctor` reports which are set; pass them as environment variables at run time if a stage needs them (`.env.example` lists the names).

## Not done

- A pre-seeded real room: `scans/` holds only the authored `hero_kitchen`, because no real kitchen has been scanned (P2). The page shows the hero kitchen until one is added.
- TLS itself, the domain and a browser smoke test (Playwright). These need the host.
