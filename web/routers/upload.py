"""
web/routers/upload.py — Router xu ly upload video va quan ly job.

Endpoint:
  POST /upload     — Nhan file video, tao job, chay detector background.
  GET  /job/{id}   — Kiem tra trang thai cua 1 job.
  GET  /jobs       — Liet ke tat ca job.

Luong xu ly:
  1. Nguoi dung gui file video qua form HTML.
  2. Server luu file vao thu muc uploads/.
  3. Tao Job moi voi job_id ngau nhien.
  4. Khoi dong Background Thread chay detector.process_video().
  5. Tra ve job_id cho browser.
  6. Browser dung job_id de ket noi WebSocket /ws/{job_id}.
"""

import os
import threading
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from web import job_manager as jm
from web.database import insert_violation

# Import detector — lazy de tranh load model khi import module
# Model chi duoc load 1 lan duy nhat va tai su dung cho moi job
_detector = None

# Thu muc goc cua project
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Thu muc luu video upload
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()


# ==========================================================
# KHOI TAO DETECTOR (Singleton — chi load model 1 lan)
# ==========================================================

def _get_detector():
    """
    Tra ve detector duy nhat cua app.
    Load model YOLO lan dau goi, tai su dung cho moi job sau do.
    Pattern nay goi la Singleton — dam bao chi co 1 instance.
    """
    global _detector
    if _detector is None:
        from detection.detector import HelmetViolationDetector
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "best.pt"
        )
        _detector = HelmetViolationDetector(
            model_path=model_path,
            save_dir=os.path.join(BASE_DIR, "violations"),
        )
    return _detector


# ==========================================================
# BACKGROUND WORKER — Chay trong thread rieng
# ==========================================================

def _run_detector_job(job: jm.Job):
    """
    Ham nay chay trong 1 Background Thread rieng biet.
    Khong duoc goi truc tiep — chi duoc goi qua threading.Thread.

    Quy trinh:
      1. Lay detector (singleton).
      2. Tao on_frame callback: moi frame -> dat vao job queue.
      3. Tao on_violation callback: vi pham -> luu DB + dat vao queue.
      4. Chay detector.process_video() — block cho den khi xong.
      5. Dat tin hieu "done" vao queue.
    """
    job.status = jm.JOB_RUNNING
    print(f"[Worker] Bat dau job {job.job_id} | Video: {job.video_name}")

    try:
        detector = _get_detector()

        # --- Callback 1: Moi frame xu ly xong ---
        # on_frame nhan bytes cua frame JPEG
        # put_frame ma hoa sang base64 roi dat vao queue
        def on_frame(frame_bytes: bytes):
            jm.put_frame(job, frame_bytes)

        # --- Callback 2: Khi phat hien vi pham ---
        # violation_dict chua: bike_id, timestamp, confidence, paths
        def on_violation(bike_id: int, timestamp: str, confidence: float, paths: dict):
            # Luu vao SQLite
            v = insert_violation(
                bike_id        = bike_id,
                timestamp      = timestamp,
                confidence     = confidence,
                image_raw      = paths.get("raw", ""),
                image_annotated= paths.get("annotated", ""),
                video_name     = job.video_name,
            )
            # Gui thong tin vi pham len browser qua WebSocket
            jm.put_violation(job, v.to_dict())

        # Gan callback vao detector
        detector.on_violation = on_violation

        # Chay xu ly video — block o day cho den khi video ket thuc
        detector.process_video(
            video_path=job.video_path,
            display=False,
            on_frame=on_frame,
        )

        # Bao hieu ket thuc thanh cong
        jm.put_done(job)

    except Exception as e:
        error_msg = f"Loi xu ly video: {str(e)}"
        print(f"[Worker] LOI job {job.job_id}: {error_msg}")
        jm.put_error(job, error_msg)


# ==========================================================
# ENDPOINTS
# ==========================================================

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    POST /upload — Nhan file video tu browser.

    - Kiem tra dinh dang file (chi chap nhan video).
    - Luu file vao uploads/.
    - Tao job moi.
    - Khoi dong background thread chay detector.
    - Tra ve job_id de browser dung ket noi WebSocket.

    Returns:
        {"job_id": "a3f9b2c1", "video_name": "giaothong_1.mp4", "status": "running"}
    """
    # Kiem tra dinh dang file
    allowed_types = ["video/mp4", "video/avi", "video/mov", "video/mkv", "video/x-msvideo"]
    if file.content_type and file.content_type not in allowed_types:
        # Neu content_type khong ro, cho qua (mot so browser gui sai content_type)
        pass

    # Kiem tra extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(
            status_code=400,
            detail=f"Dinh dang file khong ho tro: {ext}. Chi chap nhan mp4, avi, mov, mkv."
        )

    # Luu file vao thu muc uploads/
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    print(f"[Upload] Da luu video: {save_path} ({len(content) // 1024} KB)")

    # Tao job moi
    job = jm.create_job(video_name=file.filename, video_path=save_path)

    # Khoi dong background thread — KHONG doi cho xong
    thread = threading.Thread(
        target=_run_detector_job,
        args=(job,),
        daemon=True,   # Thread tu dong ket thuc khi app dong
    )
    thread.start()

    return JSONResponse({
        "job_id"    : job.job_id,
        "video_name": job.video_name,
        "status"    : job.status,
        "ws_url"    : f"/ws/{job.job_id}",
    })


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """
    GET /job/{job_id} — Kiem tra trang thai cua 1 job.

    Returns:
        {"job_id": "...", "status": "running", "total_violations": 3}
    """
    job = jm.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Khong tim thay job: {job_id}")

    return {
        "job_id"           : job.job_id,
        "video_name"       : job.video_name,
        "status"           : job.status,
        "total_violations" : job.total_violations,
        "error_message"    : job.error_message,
    }


@router.get("/jobs")
async def list_all_jobs():
    """
    GET /jobs — Liet ke tat ca job.
    """
    return {"jobs": jm.list_jobs()}
