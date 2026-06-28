import threading
import time
import uuid
from collections.abc import Callable


JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def create_job(kind: str, owner: str, label: str) -> str:
    job_id = uuid.uuid4().hex

    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "kind": kind,
            "owner": owner,
            "label": label,
            "status": "queued",
            "step": "Queued",
            "success": None,
            "message": "",
            "created_at": time.time(),
            "updated_at": time.time()
        }

    return job_id


def update_job(job_id: str, **fields):
    with JOBS_LOCK:
        job = JOBS.get(job_id)

        if not job:
            return

        job.update(fields)
        job["updated_at"] = time.time()


def get_job(job_id: str, owner: str | None = None) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)

        if not job:
            return None

        if owner and job.get("owner") != owner:
            return None

        return dict(job)


def latest_job(owner: str) -> dict | None:
    with JOBS_LOCK:
        owner_jobs = [
            job
            for job in JOBS.values()
            if job.get("owner") == owner
        ]

        if not owner_jobs:
            return None

        return dict(
            max(owner_jobs, key=lambda job: job.get("updated_at", 0))
        )


def run_background_job(
    job_id: str,
    target: Callable[[str], None]
):
    thread = threading.Thread(
        target=target,
        args=(job_id,),
        daemon=True
    )
    thread.start()
    return thread
