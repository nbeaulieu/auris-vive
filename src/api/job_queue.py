"""
Job queue — SDD-006 (pending)

Receives submitted jobs from the API layer, allocates output directories,
dispatches to runner.run(), and persists status for polling/WebSocket clients.

Current thinking: asyncio.Queue for dev (in-process), Celery + Redis for
production.  Decision deferred to SDD-006 / Q-API-2.

The interface below is what the routes layer will call regardless of the
backing implementation.
"""

from __future__ import annotations

import dataclasses
import enum
from pathlib import Path


class JobStatus(str, enum.Enum):
    QUEUED     = "queued"
    PROCESSING = "processing"
    COMPLETE   = "complete"
    FAILED     = "failed"


@dataclasses.dataclass
class Job:
    id: str
    status: JobStatus
    source_path: Path
    output_dir: Path
    error: str | None = None


async def enqueue(source_path: Path) -> Job:
    raise NotImplementedError("SDD-006 pending")


async def get_job(job_id: str) -> Job | None:
    raise NotImplementedError("SDD-006 pending")
