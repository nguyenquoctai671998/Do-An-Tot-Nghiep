"""
web/job_manager.py — Quan ly cac phien xu ly video (Job).

Moi lan nguoi dung upload video, he thong tao 1 Job voi job_id rieng.
Job chua:
  - Queue de truyen du lieu giua Detector thread va WebSocket handler.
  - Trang thai hien tai (dang chay, xong, loi).

Tai sao can module nay?
  FastAPI xu ly moi request doc lap nhau. De Detector (chay trong thread)
  co the gui du lieu sang WebSocket handler (chay trong async), 
  ta can 1 "buu dien trung gian" -> do chinh la queue trong moi Job.
"""

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
    """
    Dai dien cho 1 phien xu ly video.

    Attributes:
        job_id      : Ma dinh danh duy nhat (VD: "a3f9b2c1").
        video_name  : Ten file video goc (VD: "giaothong_1.mp4").
        video_path  : Duong dan day du den file video tren server.
        status      : Trang thai hien tai cua job.
        data_queue  : Hang doi chua du lieu gui cho WebSocket.
                      Detector thread dat vao, WebSocket handler doc ra.
        total_violations: So vi pham da phat hien.
        error_message   : Mo ta loi neu job co trang thai "error".
    """
    job_id          : str
    video_name      : str
    video_path      : str
    status          : str = JOB_PENDING
    data_queue      : queue.Queue = field(default_factory=queue.Queue)
    total_violations: int = 0
    error_message   : Optional[str] = None


# ==========================================================
# KHO LUU JOB (bo nho RAM — du cho demo)
# ==========================================================

# Dict luu tat ca job dang chay va da xong.
# Key = job_id, Value = Job object.
# Luu trong RAM nen se mat khi restart app — OK cho demo.
_jobs: Dict[str, Job] = {}


# ==========================================================
# API CONG KHAI
# ==========================================================

def create_job(video_name: str, video_path: str) -> Job:
    """
    Tao 1 Job moi va dang ky vao kho.

    Args:
        video_name: Ten file video goc.
        video_path: Duong dan file da luu tren server.

    Returns:
        Job moi voi job_id ngau nhien (8 ky tu hex).
    """
    job_id = uuid.uuid4().hex[:8]   # Vi du: "a3f9b2c1"
    job = Job(job_id=job_id, video_name=video_name, video_path=video_path)
    _jobs[job_id] = job
    print(f"[JobManager] Tao job moi: {job_id} | Video: {video_name}")
    return job


def get_job(job_id: str) -> Optional[Job]:
    """
    Lay Job theo job_id.

    Returns:
        Job object neu tim thay, None neu khong co.
    """
    return _jobs.get(job_id)


def list_jobs() -> list:
    """
    Lay danh sach tat ca job (dang chay + da xong).
    Tra ve list dict de de chuyen sang JSON.
    """
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
    """
    Dat 1 frame vao hang doi cua Job.
    Duoc goi boi Detector thread moi khi co frame moi.

    Dinh dang message:
        {"type": "frame", "data": "<base64 cua JPEG bytes>"}
    """
    import base64
    job.data_queue.put({
        "type": "frame",
        "data": base64.b64encode(frame_bytes).decode("utf-8"),
    })


def put_violation(job: Job, violation_dict: dict) -> None:
    """
    Dat thong tin vi pham vao hang doi cua Job.
    Duoc goi boi on_violation callback trong Detector.

    Dinh dang message:
        {"type": "violation", "id": 1, "bike_id": 5, ...}
    """
    job.total_violations += 1
    job.data_queue.put({
        "type"     : "violation",
        "data"     : violation_dict,
    })


def put_done(job: Job) -> None:
    """
    Dat tin hieu "da xong" vao hang doi.
    WebSocket handler nhan duoc tin hieu nay se dong ket noi.
    """
    job.status = JOB_DONE
    job.data_queue.put({
        "type" : "done",
        "total": job.total_violations,
    })
    print(f"[JobManager] Job {job.job_id} hoan tat. Tong vi pham: {job.total_violations}")


def put_error(job: Job, message: str) -> None:
    """
    Dat thong bao loi vao hang doi.
    """
    job.status = JOB_ERROR
    job.error_message = message
    job.data_queue.put({
        "type"   : "error",
        "message": message,
    })
    print(f"[JobManager] Job {job.job_id} gap loi: {message}")
