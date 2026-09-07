"""
web/routers/violations.py — API quan ly vi pham (CRUD).

Endpoints:
  GET    /api/violations            — Lay danh sach (co the filter)
  GET    /api/violations/{id}       — Lay 1 vi pham cu the
  PATCH  /api/violations/{id}/confirm — Xac nhan la vi pham that
  PATCH  /api/violations/{id}/reject  — Huy bo vi pham
  GET    /api/stats                 — Thong ke tong quan
  GET    /images/{filename}         — Tra ve file anh bang chung

Tai sao dung PATCH thay vi PUT?
  PUT = thay the toan bo object.
  PATCH = cap nhat 1 phan (chi doi status).
  => PATCH phu hop hon cho hanh dong "xac nhan" va "huy".
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from web.database import (
    get_all_violations, get_violation_by_id,
    update_status, get_stats,
)
from web.models import STATUS_CONFIRMED, STATUS_REJECTED

# Thu muc chua anh bang chung
VIOLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "violations"
)

router = APIRouter(prefix="/api")


# ==========================================================
# ENDPOINTS
# ==========================================================

@router.get("/violations")
async def list_violations(status: Optional[str] = None):
    """
    GET /api/violations?status=pending

    Lay danh sach vi pham. Co the loc theo status.

    Query params:
        status: "pending" | "confirmed" | "rejected" | (bo trong = tat ca)

    Returns:
        {"violations": [...], "count": 5}
    """
    violations = get_all_violations(status_filter=status)
    return {
        "violations": [v.to_dict() for v in violations],
        "count"     : len(violations),
    }


@router.get("/violations/{violation_id}")
async def get_violation(violation_id: int):
    """
    GET /api/violations/{id} — Lay thong tin 1 vi pham.

    Returns:
        Violation dict neu tim thay, 404 neu khong co.
    """
    v = get_violation_by_id(violation_id)
    if not v:
        raise HTTPException(
            status_code=404,
            detail=f"Khong tim thay vi pham ID={violation_id}"
        )
    return v.to_dict()


@router.patch("/violations/{violation_id}/confirm")
async def confirm_violation(violation_id: int):
    """
    PATCH /api/violations/{id}/confirm — Xac nhan vi pham la that.

    Doi status tu "pending" sang "confirmed".
    Vi pham van con trong danh sach, chi thay doi mau trang thai.

    Returns:
        Vi pham da cap nhat.
    """
    v = update_status(violation_id, STATUS_CONFIRMED)
    if not v:
        raise HTTPException(
            status_code=404,
            detail=f"Khong tim thay vi pham ID={violation_id}"
        )
    return {"message": "Da xac nhan vi pham.", "violation": v.to_dict()}


@router.patch("/violations/{violation_id}/reject")
async def reject_violation(violation_id: int):
    """
    PATCH /api/violations/{id}/reject — Huy bo vi pham.

    Doi status tu "pending" sang "rejected".
    Vi pham van con trong danh sach, chi thay doi mau trang thai.

    Returns:
        Vi pham da cap nhat.
    """
    v = update_status(violation_id, STATUS_REJECTED)
    if not v:
        raise HTTPException(
            status_code=404,
            detail=f"Khong tim thay vi pham ID={violation_id}"
        )
    return {"message": "Da huy bo vi pham.", "violation": v.to_dict()}


@router.get("/stats")
async def get_dashboard_stats():
    """
    GET /api/stats — Thong ke tong quan cho dashboard header.

    Returns:
        {"total": 10, "pending": 3, "confirmed": 6, "rejected": 1}
    """
    stats = get_stats()
    return stats.to_dict()


@router.delete("/violations/{violation_id}")
async def delete_violation_endpoint(violation_id: int):
    """
    DELETE /api/violations/{id} — Xoa 1 vi pham khoi he thong.
    Dong thoi don dep file anh bang chung tren dia neu co.
    """
    from web.database import delete_violation
    
    # Lay thong tin truoc khi xoa de biet duong dan anh
    v = get_violation_by_id(violation_id)
    if not v:
        raise HTTPException(
            status_code=404,
            detail=f"Khong tim thay vi pham ID={violation_id}"
        )

    # Xoa file anh bang chung tren dia
    for img_path in [v.image_raw, v.image_annotated]:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception as e:
                print(f"[Delete] Khong the xoa file anh {img_path}: {e}")

    # Xoa ban ghi khoi SQLite
    deleted = delete_violation(violation_id)
    if not deleted:
        raise HTTPException(
            status_code=500,
            detail="Khong the xoa ban ghi khoi database."
        )

    return {"message": f"Da xoa vi pham #{violation_id} thanh cong.", "id": violation_id}


@router.post("/violations/clear")
async def clear_violations_endpoint(status: Optional[str] = None):
    """
    POST /api/violations/clear?status=rejected — Don dep du lieu vi pham.
    - Neu status = "rejected": chi xoa cac vi pham da bi huy
    - Neu status = None / "": xoa toan bo vi pham
    """
    from web.database import clear_violations

    if status and status not in ["pending", "confirmed", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail=f"Trang thai khong hop le: {status}"
        )

    count = clear_violations(status_filter=status if status else None)
    return {
        "message": f"Da xoa {count} ban ghi vi pham.",
        "deleted_count": count,
        "status_filtered": status or "all"
    }


# ==========================================================
# PHUC VU ANH BANG CHUNG
# ==========================================================

@router.get("/images/{filename}")
async def serve_image(filename: str):
    """
    GET /api/images/{filename} — Tra ve file anh bang chung.

    Anh duoc luu trong thu muc violations/.
    Frontend dung endpoint nay de hien anh trong dashboard.

    Bao mat: Chi cho phep ten file don gian, chan path traversal attack.
    Vi du request doc hai "../database.db" se bi tu choi.
    """
    # Bao mat: loai bo bat ky thu muc cha khoi ten file
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="Ten file khong hop le.")

    file_path = os.path.join(VIOLATIONS_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Khong tim thay anh: {safe_filename}"
        )

    return FileResponse(file_path, media_type="image/jpeg")
