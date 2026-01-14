from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable, TypedDict


class JobInfo(TypedDict, total=False):
    id: str
    type: str
    status: str  # queued|running|done|error
    createdAt: float
    startedAt: float
    finishedAt: float
    result: Any
    error: str


_JOBS: dict[str, JobInfo] = {}
_JOBS_LOCK = asyncio.Lock()


def create_job_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex}"


async def create_job(job_type: str) -> JobInfo:
    job_id = create_job_id(job_type)
    job: JobInfo = {
        "id": job_id,
        "type": job_type,
        "status": "queued",
        "createdAt": time.time(),
    }
    async with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


async def get_job(job_id: str) -> JobInfo | None:
    async with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None


async def _set_job(job_id: str, **patch: Any) -> None:
    async with _JOBS_LOCK:
        if job_id not in _JOBS:
            return
        _JOBS[job_id].update(patch)


def start_job(
    job: JobInfo,
    coro_factory: Callable[[], Awaitable[Any]],
) -> None:
    job_id = job["id"]

    async def _runner() -> None:
        await _set_job(job_id, status="running", startedAt=time.time())
        try:
            result = await coro_factory()
            await _set_job(job_id, status="done", finishedAt=time.time(), result=result)
        except Exception as e:  # noqa: BLE001
            await _set_job(job_id, status="error", finishedAt=time.time(), error=str(e))

    asyncio.create_task(_runner())
