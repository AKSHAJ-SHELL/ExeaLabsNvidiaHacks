"""Child process for one claimed job: ``python -m arrival.jobs.child JOB_DIR OUT_DIR OPTIONS_JSON``.

``arrival.jobs.worker.run_isolated`` starts this so the worker can kill a job that exceeds its wall-clock limit.
The job's own failure is recorded in ``status.json`` and does not change the exit code; a non-zero exit means the
process itself died, which the worker records as ``WorkerProcessError``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from arrival.jobs.limits import Limits
from arrival.jobs.worker import _read_status, process


def apply_memory_cap(max_bytes: int, platform: str | None = None, resource=None) -> bool:
    """Cap this process's address space (``RLIMIT_AS``) at ``max_bytes``. Linux only, and only when ``max_bytes`` > 0:
    anywhere else (macOS does not enforce RLIMIT_AS/RLIMIT_DATA) it does nothing and returns False. The cap counts
    address space, not resident memory: a 2-episode hero_kitchen job peaks at 5.7 GB of address space on 18 cores
    for 0.36 GB resident, and the address space grows with the core count. Past the cap the native libraries abort
    or segfault rather than raise ``MemoryError`` (measured in docs/ref/MEMCAP.md), so leave it off or set it at
    least 1.5 times the peak measured on the host."""
    if not max_bytes or max_bytes <= 0 or (platform or sys.platform) != "linux":
        return False
    if resource is None:
        import resource
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    cap = max_bytes if hard in (-1, resource.RLIM_INFINITY) else min(max_bytes, hard)
    resource.setrlimit(resource.RLIMIT_AS, (cap, hard))
    return True


def main(argv: list[str] | None = None) -> int:
    job_dir, out_dir, raw = (argv if argv is not None else sys.argv[1:])[:3]
    opts = json.loads(raw)
    limits = Limits(**opts.pop("limits", {}))
    apply_memory_cap(limits.max_job_bytes)
    status = _read_status(Path(job_dir))
    if status is None:
        print(f"[work] {job_dir}: no readable status.json", file=sys.stderr)
        return 3
    process(Path(job_dir), status, Path(out_dir), limits=limits, **opts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
