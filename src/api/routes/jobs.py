"""
Jobs routes — SDD-006 (pending)

REST surface for pipeline jobs.

    POST   /jobs          Submit a new job (file upload or URL)
    GET    /jobs/{id}     Poll job status + result
    WS     /jobs/{id}/ws  Real-time progress stream

All routes are stubs until Q-API-1 (auth) and Q-API-2 (job storage) are
resolved.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["jobs"])


@router.post("/")
async def submit_job() -> dict:
    raise NotImplementedError("SDD-006 pending — resolve Q-API-1 first")


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    raise NotImplementedError("SDD-006 pending")
