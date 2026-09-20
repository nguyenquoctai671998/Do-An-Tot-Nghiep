import sqlite3
import os
from typing import Optional

from web.models import Violation, Stats, STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED


# ==========================================================
# CẤU HÌNH
# ==========================================================

# Đường dẫn file SQLite — nằm ở thư mục gốc project
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")

# SQL tạo bảng — chạy 1 lần duy nhất lúc khởi động app
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS violations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_id         INTEGER NOT NULL,
    timestamp       TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    image_raw       TEXT    NOT NULL,
    image_annotated TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    video_name      TEXT    NOT NULL
);
"""


# ==========================================================
# HÀM TIỆN ÍCH NỘI BỘ
# ==========================================================

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_bike_id(val) -> int:
    """Chuyển đổi an toàn bike_id từ SQLite (kể cả khi bị lưu dạng bytes/BLOB)."""
    if isinstance(val, bytes):
        import struct
        return struct.unpack('<q', val)[0] if len(val) == 8 else int.from_bytes(val, 'little')
    try:
        return int(val)
    except Exception:
        return 0


def _row_to_violation(row: sqlite3.Row) -> Violation:
    """Chuyển 1 hàng SQLite Row thành Violation object."""
    return Violation(
        id             = row["id"],
        bike_id        = _parse_bike_id(row["bike_id"]),
        timestamp      = str(row["timestamp"]),
        confidence     = float(row["confidence"]),
        image_raw      = str(row["image_raw"]),
        image_annotated= str(row["image_annotated"]),
        status         = str(row["status"]),
        video_name     = str(row["video_name"]),
    )


# ==========================================================
# API CÔNG KHAI
# ==========================================================

def init_db() -> None:
    with _get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    print(f"[DB] Database khởi tạo tại: {DB_PATH}")


def insert_violation(
    bike_id        : int,
    timestamp      : str,
    confidence     : float,
    image_raw      : str,
    image_annotated: str,
    video_name     : str,
) -> Violation:
    sql = """
        INSERT INTO violations 
            (bike_id, timestamp, confidence, image_raw, image_annotated, status, video_name)
        VALUES 
            (?, ?, ?, ?, ?, 'pending', ?)
    """
    with _get_connection() as conn:
        cursor = conn.execute(sql, (
            bike_id, timestamp, round(confidence, 4),
            image_raw, image_annotated, video_name,
        ))
        conn.commit()
        new_id = cursor.lastrowid

    print(f"[DB] Đã lưu vi phạm mới: ID={new_id} | Xe={bike_id} | Conf={confidence:.2f}")

    return Violation(
        id             = new_id,
        bike_id        = bike_id,
        timestamp      = timestamp,
        confidence     = confidence,
        image_raw      = image_raw,
        image_annotated= image_annotated,
        status         = STATUS_PENDING,
        video_name     = video_name,
    )


def get_all_violations(status_filter: Optional[str] = None) -> list[Violation]:
    # Nếu frontend truyền chuỗi rỗng "" (khi bấm Tất Cả), coi như None (lấy tất cả)
    if status_filter == "":
        status_filter = None

    if status_filter and status_filter not in [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED]:
        raise ValueError(f"status_filter không hợp lệ: '{status_filter}'")

    if status_filter:
        sql = "SELECT * FROM violations WHERE status = ? ORDER BY id DESC"
        params = (status_filter,)
    else:
        sql = "SELECT * FROM violations ORDER BY id DESC"
        params = ()

    with _get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_violation(row) for row in rows]


def get_violation_by_id(violation_id: int) -> Optional[Violation]:
    sql = "SELECT * FROM violations WHERE id = ?"
    with _get_connection() as conn:
        row = conn.execute(sql, (violation_id,)).fetchone()
    return _row_to_violation(row) if row else None


def update_status(violation_id: int, new_status: str) -> Optional[Violation]:
    if new_status not in [STATUS_CONFIRMED, STATUS_REJECTED]:
        raise ValueError(f"Trạng thái không hợp lệ: '{new_status}'. Phải là 'confirmed' hoặc 'rejected'.")

    sql = "UPDATE violations SET status = ? WHERE id = ?"
    with _get_connection() as conn:
        cursor = conn.execute(sql, (new_status, violation_id))
        conn.commit()
        affected = cursor.rowcount

    if affected == 0:
        print(f"[DB] Không tìm thấy vi phạm ID={violation_id}")
        return None

    print(f"[DB] Cập nhật vi phạm ID={violation_id} → {new_status}")
    return get_violation_by_id(violation_id)


def get_stats() -> Stats:
    sql = """
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
            SUM(CASE WHEN status = 'rejected'  THEN 1 ELSE 0 END) AS rejected
        FROM violations
    """
    with _get_connection() as conn:
        row = conn.execute(sql).fetchone()

    return Stats(
        total    = row["total"]     or 0,
        pending  = row["pending"]   or 0,
        confirmed= row["confirmed"] or 0,
        rejected = row["rejected"]  or 0,
    )


def delete_violation(violation_id: int) -> bool:
    sql = "DELETE FROM violations WHERE id = ?"
    with _get_connection() as conn:
        cursor = conn.execute(sql, (violation_id,))
        conn.commit()
    return cursor.rowcount > 0


def clear_violations(status_filter: Optional[str] = None) -> int:
    if status_filter:
        sql = "DELETE FROM violations WHERE status = ?"
        params = (status_filter,)
    else:
        sql = "DELETE FROM violations"
        params = ()

    with _get_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
