"""
web/models.py — Định nghĩa cấu trúc dữ liệu cho toàn bộ ứng dụng.

File này KHÔNG kết nối database, KHÔNG xử lý logic.
Chỉ định nghĩa "hình dạng" của dữ liệu — dùng chung ở mọi nơi.
"""

from dataclasses import dataclass, field
from typing import Optional


# ==========================================================
# STATUS CONSTANTS — Trạng thái vi phạm
# ==========================================================
# Dùng constants thay vì string cứng để tránh lỗi typo.
# Ví dụ: STATUS_PENDING thay vì viết "pending" khắp nơi.

STATUS_PENDING   = "pending"    # Chờ xét duyệt (mới phát hiện)
STATUS_CONFIRMED = "confirmed"  # Đã xác nhận là vi phạm thật
STATUS_REJECTED  = "rejected"   # Đã hủy (nhận diện sai / không rõ)

ALL_STATUSES = [STATUS_PENDING, STATUS_CONFIRMED, STATUS_REJECTED]


# ==========================================================
# DATACLASS: Violation — Một bản ghi vi phạm
# ==========================================================

@dataclass
class Violation:
    """
    Đại diện cho 1 trường hợp vi phạm không đội mũ bảo hiểm.

    Ánh xạ 1-1 với 1 hàng trong bảng `violations` của SQLite.

    Attributes:
        id              : Khóa chính, SQLite tự tăng (None khi chưa lưu vào DB).
        bike_id         : Track ID của xe máy từ ByteTrack.
        timestamp       : Chuỗi thời gian phát hiện, ví dụ "20260831-201532_045".
        confidence      : Độ tự tin của nhãn no-helmet (0.0 – 1.0).
        image_raw       : Đường dẫn tới ảnh gốc (chưa khoanh vùng).
        image_annotated : Đường dẫn tới ảnh đã khoanh vùng đỏ.
        status          : Trạng thái duyệt: "pending" | "confirmed" | "rejected".
        video_name      : Tên file video nguồn, ví dụ "giaothong_1.mp4".
    """

    bike_id         : int
    timestamp       : str
    confidence      : float
    image_raw       : str
    image_annotated : str
    video_name      : str
    status          : str = STATUS_PENDING  # Mặc định là chờ duyệt
    id              : Optional[int] = None  # None = chưa lưu vào DB

    def to_dict(self) -> dict:
        """
        Chuyển thành dict — dùng khi trả JSON về cho frontend.
        Lưu ý: ép kiểu tường minh để tránh numpy.int64/float32/bytes
        không serialize được sang JSON qua WebSocket.
        """
        bike_id_val = self.bike_id
        if isinstance(bike_id_val, bytes):
            import struct
            bike_id_val = struct.unpack('<q', bike_id_val)[0] if len(bike_id_val) == 8 else int.from_bytes(bike_id_val, 'little')
        else:
            try:
                bike_id_val = int(bike_id_val)
            except Exception:
                bike_id_val = 0

        return {
            "id"             : int(self.id) if self.id is not None else None,
            "bike_id"        : bike_id_val,
            "timestamp"      : str(self.timestamp),
            "confidence"     : round(float(self.confidence), 4),
            "image_raw"      : str(self.image_raw),
            "image_annotated": str(self.image_annotated),
            "status"         : str(self.status),
            "video_name"     : str(self.video_name),
        }

    @property
    def status_label(self) -> str:
        """Nhãn hiển thị tiếng Việt cho trạng thái."""
        return {
            STATUS_PENDING  : "Cho duyet",
            STATUS_CONFIRMED: "Xac nhan",
            STATUS_REJECTED : "Da huy",
        }.get(self.status, self.status)

    @property
    def status_badge_class(self) -> str:
        """Bootstrap badge class tương ứng với trạng thái — dùng trong HTML template."""
        return {
            STATUS_PENDING  : "bg-warning text-dark",
            STATUS_CONFIRMED: "bg-success",
            STATUS_REJECTED : "bg-danger",
        }.get(self.status, "bg-secondary")


# ==========================================================
# DATACLASS: Stats — Thống kê tổng quan cho dashboard
# ==========================================================

@dataclass
class Stats:
    """
    Số liệu thống kê tổng hợp — hiển thị ở đầu trang dashboard.

    Attributes:
        total     : Tổng số vi phạm đã phát hiện.
        pending   : Số đang chờ duyệt.
        confirmed : Số đã xác nhận.
        rejected  : Số đã hủy.
    """

    total    : int = 0
    pending  : int = 0
    confirmed: int = 0
    rejected : int = 0

    def to_dict(self) -> dict:
        return {
            "total"    : self.total,
            "pending"  : self.pending,
            "confirmed": self.confirmed,
            "rejected" : self.rejected,
        }
