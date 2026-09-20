import queue
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict


# ==========================================================
# TRANG THAI JOB
# ==========================================================

JOB_PENDING = "pending"   # Cho xu ly
JOB_RUNNING = "running"   # Dang chay detector
JOB_DONE    = "done"      # Hoan tat
JOB_ERROR   = "error"     # Gap loi


# ==========================================================
# DATACLASS: Job
# ==========================================================

@dataclass
class Job:
    job_id          : str
    video_name      : str
    video_path      : str
    status          : str = JOB_PENDING
    data_queue      : queue.Queue = field(default_factory=queue.Queue)
    total_violations: int = 0
    error_message   : Optional[str] = None


_jobs: Dict[str, Job] = {}


# ==========================================================
# API CONG KHAI
# ==========================================================

def create_job(video_name: str, video_path: str) -> Job:
    job_id = uuid.uuid4().hex[:8]   # Vi du: "a3f9b2c1"
    job = Job(job_id=job_id, video_name=video_name, video_path=video_path)
    _jobs[job_id] = job
    print(f"[JobManager] Tao job moi: {job_id} | Video: {video_name}")
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def list_jobs() -> list:
    return [
        {
            "job_id"           : j.job_id,
            "video_name"       : j.video_name,
            "status"           : j.status,
            "total_violations" : j.total_violations,
        }
        for j in _jobs.values()
    ]


def put_frame(job: Job, frame_bytes: bytes) -> None:
    import base64
    job.data_queue.put({
        "type": "frame",
        "data": base64.b64encode(frame_bytes).decode("utf-8"),
    })


def put_violation(job: Job, violation_dict: dict) -> None:
    job.total_violations += 1
    job.data_queue.put({
        "type"     : "violation",
        "data"     : violation_dict,
    })


def put_done(job: Job) -> None:
    job.status = JOB_DONE
    job.data_queue.put({
        "type" : "done",
        "total": job.total_violations,
    })
    print(f"[JobManager] Job {job.job_id} hoan tat. Tong vi pham: {job.total_violations}")


def put_error(job: Job, message: str) -> None:
    job.status = JOB_ERROR
    job.error_message = message
    job.data_queue.put({
        "type"   : "error",
        "message": message,
    })
    print(f"[JobManager] Job {job.job_id} gap loi: {message}")
