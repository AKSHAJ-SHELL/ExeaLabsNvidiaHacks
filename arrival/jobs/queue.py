"""Local job queue: store an upload and write a queued status record.

There is no worker that drains this queue tonight. The status JSON is the
whole API. This module must not import the compiler or generator.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

MAX_UPLOAD_BYTES = 200 * 1024 * 1024


def check_upload_size(content_length: int, limit: int = MAX_UPLOAD_BYTES) -> bool:
    """Return True if an upload of ``content_length`` bytes is accepted."""
    return 0 <= int(content_length) <= int(limit)


def new_job_id() -> str:
    return "job_" + uuid.uuid4().hex[:8]


def create_job(jobs_root: Path, filename: str, data: bytes) -> dict:
    """Write ``<jobs_root>/<id>/upload.bin`` and ``status.json``; return the status."""
    jobs_root = Path(jobs_root)
    job_id = new_job_id()
    job_dir = jobs_root / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    (job_dir / "upload.bin").write_bytes(data)
    status = {
        "id": job_id,
        "status": "queued",
        "created_unix": int(time.time()),
        "filename": Path(filename or "upload.bin").name,
        "bytes": len(data),
    }
    (job_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    return status


def read_job(jobs_root: Path, job_id: str) -> dict | None:
    path = Path(jobs_root) / job_id / "status.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())
