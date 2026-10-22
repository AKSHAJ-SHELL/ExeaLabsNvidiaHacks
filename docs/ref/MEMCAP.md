# Job memory cap on Linux: measured

`ARRIVAL_MAX_JOB_MB` sets `RLIMIT_AS` on a job's child process (`arrival/jobs/child.py`). Until now it was only checked with a bare `bytearray` (`tests/test_jobs_ops.py::test_memory_cap_makes_a_big_allocation_fail`). These are the numbers for a real job.

## Setup

- Ubuntu 24.04.5 in Docker (linux/aarch64, 18 CPUs, 8 GB), Python 3.12.3, MuJoCo 3.16.0, `MUJOCO_GL=egl`.
- The job: `scans/hero_kitchen/scan.json` through `run_once(isolate=True)` with 2 episodes of `counter_to_sink`, 1 person, res 64 and `job_retries=0`.
- The child is the worker's own `python -m arrival.jobs.child`, wrapped to record `/proc/self/status` `VmPeak` (address space) and `VmHWM` (peak resident memory) at exit.

## Address space, not memory

With no cap the job finishes 2/2 in 42 s. Its child peaks at 5.7 GB of address space but only 0.36 GB resident.

| Run | Peak address space (VmPeak) | Peak resident (VmHWM) |
|---|---:|---:|
| 18 CPUs | 5.70 GB | 0.36 GB |
| 18 CPUs, `MALLOC_ARENA_MAX=2` | 2.64 GB | 0.36 GB |
| 2 CPUs (`--cpuset-cpus=0,1`) | 2.38 GB | 0.35 GB |
| 2 CPUs, `MALLOC_ARENA_MAX=2` | 1.82 GB | 0.35 GB |

Resident memory is the same in every run. The address space follows the CPU count, because each thread pool gets its own glibc malloc arena and stacks. So a value of `ARRIVAL_MAX_JOB_MB` that works on one server kills the same job on a server with more cores.

## Under the cap

18 CPUs, the same job, one run per cap:

| `ARRIVAL_MAX_JOB_MB` | Result | Recorded error |
|---:|---|---|
| 8192 | done, 2/2 | |
| 6144 | done, 2/2 | |
| 5120 | failed | `WorkerProcessError: the job's process exited with code -6 during stage 'sim'` (SIGABRT) |
| 4096 | failed | `ArrowException: Unknown error: Failed to launch worker thread: Resource temporarily unavailable` |
| 3072 | failed | `WorkerProcessError: ... exited with code -11` (SIGSEGV) |
| 2048 | failed | `WorkerProcessError: ... exited with code -6` (SIGABRT) |
| 1024 | failed | `unsupported layout: no task can run in this room: RuntimeError: Caught an unknown exception! (at renderer.py:81); ValueError: Error: Could not allocate memory ...` |
| 512 | failed | `WorkerProcessError: ... exited with code 1 during stage None` |

None of these is the `MemoryError` that `child.py` described. The native libraries (MuJoCo, the EGL renderer, Arrow, the video encoder) abort, segfault or raise their own errors when an allocation is refused. At 1024 MB the failure is reported to the uploader as an unsupported room layout.

## What this means

`RLIMIT_AS` can't serve as a memory limit for these jobs. The right value depends on the host's core count, and going over it crashes the job instead of failing it with a clear reason.

## The limit now: resident memory, checked by the worker

`ARRIVAL_MAX_JOB_MB` now limits resident memory. Every 0.5 s (`MEM_TICK`), `run_isolated` reads the resident memory of the child and every process under it with `arrival.jobs.worker.tree_rss` (`/proc` on Linux, `ps` elsewhere). Past the limit it kills the child, records `MemoryLimitError: the job used N MB resident, over the M MB limit (ARRIVAL_MAX_JOB_MB), during stage '...'` and does not retry, the same as a timeout. `child.py` no longer sets `RLIMIT_AS`.

The same job and image, with the new limit:

| `ARRIVAL_MAX_JOB_MB` | 18 CPUs | 2 CPUs |
|---:|---|---|
| off | done, 2/2, 42 s | |
| 2048 | done, 2/2 | |
| 1024 | done, 2/2 | |
| 600 | done, 2/2 | done, 2/2, 69 s |
| 300 | failed after 21 s: `MemoryLimitError: the job used 337 MB resident, over the 300 MB limit (ARRIVAL_MAX_JOB_MB), during stage 'sim'` | failed after 16 s, the same error |

The job uses the same memory on both hosts, so one value works on both. Leave headroom over the roughly 365 MB this small job peaks at. Longer jobs, more people or a higher `--res` use more, so set it from a run of the job sizes you serve.

## Limits of the check

- It samples every 0.5 s, so a spike shorter than that can pass unseen. The check stops runaway growth; it does not guarantee a hard ceiling.
- It needs the child process: with `max_job_seconds` 0 (`isolate` off) the job runs in the worker and nothing is checked.
- Windows was not measured; `tree_rss` uses `ps` there, which a stock Windows doesn't have, so the check reads nothing and never kills.
