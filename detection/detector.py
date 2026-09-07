"""
detector.py — Module nhận diện vi phạm không đội mũ bảo hiểm
Refactored từ script gốc: tổ chức thành class, dễ tích hợp với web backend.
"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import cv2
from ultralytics import YOLO



# CẤU HÌNH MẶC ĐỊNH
DEFAULT_MODEL_PATH    = "best.pt"
DEFAULT_SAVE_DIR      = "violations"
DEFAULT_CONF          = 0.45
DEFAULT_IMGSZ         = 640
VIOLATION_MARGIN      = 0.15

ALLOWED_CLASS_NAMES   = ["motobike", "helmet", "no-helmet"]

# Màu sắc (BGR)
COLOR_NEW_VIOLATOR      = (0, 0, 255)   # Đỏ  — vi phạm mới
COLOR_CAPTURED_VIOLATOR = (0, 255, 0)   # Xanh lá — đã ghi nhận, bám theo


# HÀM BỔ TRỢ
def is_overlapping(box1, box2) -> bool:
    #Kiểm tra 2 Bounding Box có giao nhau không (IoU-free, nhanh hơn).
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    return (min(x2_1, x2_2) > max(x1_1, x1_2) and
            min(y2_1, y2_2) > max(y1_1, y1_2))


def draw_box(img, box, label: str, color: tuple):
    #Vẽ Bounding Box + nhãn, tự co giãn theo độ phân giải. Trả về img đã vẽ (in-place).
    h_img, w_img = img.shape[:2]
    font_scale  = max(0.4, min(w_img, h_img) / 1000.0)
    thickness   = max(1, int(min(w_img, h_img) / 400.0))
    box_thick   = max(2, int(min(w_img, h_img) / 350.0))

    x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, box_thick)

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    bg_y1 = max(0, y1 - th - 10)
    bg_y2 = max(th + 10, y1)
    cv2.rectangle(img, (x1, bg_y1), (x1 + tw + 6, bg_y2), color, -1)
    cv2.putText(img, label, (x1 + 3, bg_y2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
    return img


def draw_dashboard(img, total: int):
    #Vẽ bảng đếm tổng vi phạm ở góc trái trên cùng.
    h_img, w_img = img.shape[:2]
    fs    = max(0.6, min(w_img, h_img) / 800.0)
    thick = max(2, int(min(w_img, h_img) / 400.0))
    text  = f"Tổng vi phạm: {total}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, thick)
    cv2.rectangle(img, (15, 15), (25 + tw, 25 + th + 10), (0, 0, 0), -1)
    cv2.putText(img, text, (20, 20 + th),
                cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 255, 255), thick)


def _make_timestamp() -> str:
    #Tạo timestamp không trùng lặp (đến millisecond).
    return time.strftime("%Y%m%d-%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"


def _save_pair(raw_img, detail_img, bike_id: int, timestamp: str, save_dir: str) -> dict:
    #Lưu cặp ảnh bằng chứng (ảnh gốc + ảnh khoanh vùng). Trả về dict chứa đường dẫn 2 file để caller biết kết quả.
    try:
        fs_path = os.path.join(save_dir, f"{timestamp}_raw_ID{bike_id}.jpg")
        dt_path = os.path.join(save_dir, f"{timestamp}_annotated_ID{bike_id}.jpg")
        ok_raw  = cv2.imwrite(fs_path, raw_img)
        ok_det  = cv2.imwrite(dt_path, detail_img)
        if not (ok_raw and ok_det):
            raise IOError("cv2.imwrite trả về False — kiểm tra đường dẫn hoặc dung lượng ổ đĩa.")
        return {"raw": fs_path, "annotated": dt_path}
    except Exception as e:
        print(f"[ERROR] Lưu ảnh vi phạm thất bại (ID {bike_id}): {e}")
        return {}


# HelmetViolationDetector
class HelmetViolationDetector:
    """
    Logic nhận diện vi phạm.
    Thiết kế tích hợp vào web backend (FastAPI):
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        save_dir:   str = DEFAULT_SAVE_DIR,
        conf:       float = DEFAULT_CONF,
        imgsz:      int   = DEFAULT_IMGSZ,
        on_violation=None, 
    ):
        self.save_dir  = save_dir
        self.conf      = conf
        self.imgsz     = imgsz
        self.on_violation = on_violation  # hook cho web backend

        os.makedirs(save_dir, exist_ok=True)

        print(f"[Detector] Đang tải model: {model_path}")
        self.model = YOLO(model_path)

        # Lọc chỉ các class cần thiết
        self.target_class_ids = [
            cid for cid, name in self.model.names.items()
            if name in ALLOWED_CLASS_NAMES
        ]

        # Trạng thái tracking — reset mỗi lần process_video() được gọi
        self._captured_ids: set = set()
        self.total_violators: int = 0

        # ThreadPool dùng chung — tránh tạo quá nhiều thread
        self._executor = ThreadPoolExecutor(max_workers=4)

        print(f"[Detector] Khởi động xong. Class IDs: {self.target_class_ids}")

    # API chính: xử lý 1 video
    def process_video(self, video_path: str, display: bool = False, on_frame=None):
        """
        Xu ly toan bo video, phat hien vi pham, luu anh.

        Args:
            video_path : Duong dan toi file video.
            display    : True -> mo cua so OpenCV (dung khi chay standalone).
            on_frame   : Callback(frame_bytes: bytes) duoc goi moi N frame.
                         Web backend truyen ham nay de nhan frame qua WebSocket.
                         None -> khong stream frame (standalone mode).
        """
        # Reset trang thai cho moi video moi
        self._captured_ids.clear()
        self.total_violators = 0

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"[ERROR] Khong the mo video: {video_path}")
            return

        # Gioi han frame gui di de tranh qua tai bang thong
        # Chi gui 1 frame moi STREAM_EVERY frame xu ly
        STREAM_EVERY = 2
        frame_count  = 0

        print(f"[Detector] Bat dau xu ly: {video_path}")
        if display:
            print("[Detector] Bam 'q' tren cua so video de dung.")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("[Detector] Da doc het video.")
                break

            frame_count += 1
            raw_frame  = frame.copy()   # Anh goc - luu bang chung khong ve
            live_frame = frame.copy()   # Anh hien thi - co ve bounding box

            live_frame = self._process_frame(raw_frame, live_frame)
            draw_dashboard(live_frame, self.total_violators)

            # --- Gui frame ve browser qua WebSocket ---
            # Chi gui moi STREAM_EVERY frame de giam tai bang thong.
            # JPEG quality=70 la can bang giua chat luong va toc do.
            if on_frame and (frame_count % STREAM_EVERY == 0):
                ok, buffer = cv2.imencode(".jpg", live_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    on_frame(buffer.tobytes())

            # --- Hien thi cua so OpenCV (standalone mode) ---
            if display:
                cv2.imshow("Traffic Hệ thống xử lý vi phạm quy định đội mũ bảo hiểm", live_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("[Detector] Nguoi dung yeu cau dung.")
                    break

        cap.release()
        if display:
            cv2.destroyAllWindows()
        print(f"[Detector] Hoan tat! Tong vi pham: {self.total_violators}")

    # ----------------------------------------------------------
    # Xử lý từng frame
    # ----------------------------------------------------------

    def _process_frame(self, raw_frame, live_frame):
        """Chạy inference + tracking trên 1 frame, cập nhật live_frame."""
        results = self.model.track(
            source=raw_frame,
            conf=self.conf,
            imgsz=self.imgsz,
            classes=self.target_class_ids,
            tracker="bytetrack.yaml",
            persist=True,
            verbose=False,
        )

        if results[0].boxes is None or len(results[0].boxes) == 0:
            return live_frame

        boxes = results[0].boxes
        clss      = boxes.cls.cpu().numpy().astype(int)
        confs     = boxes.conf.cpu().numpy()
        xyxys     = boxes.xyxy.cpu().numpy()
        track_ids = (
            [int(x) for x in boxes.id.cpu().numpy()]
            if boxes.id is not None
            else [None] * len(clss)
        )

        motobikes, helmets, no_helmets = [], [], []
        for xyxy, conf, cls_id, tid in zip(xyxys, confs, clss, track_ids):
            name = self.model.names[cls_id]
            obj  = {"xyxy": xyxy, "conf": float(conf), "id": tid, "class": name}
            if name == "motobike":   motobikes.append(obj)
            elif name == "helmet":   helmets.append(obj)
            elif name == "no-helmet": no_helmets.append(obj)

        for mb in motobikes:
            live_frame = self._handle_motobike(mb, helmets, no_helmets, raw_frame, live_frame)

        return live_frame

    # ----------------------------------------------------------
    # Logic nghiệp vụ: xét vi phạm từng xe
    # ----------------------------------------------------------

    def _handle_motobike(self, mb, helmets, no_helmets, raw_frame, live_frame):
        mb_id   = mb["id"]
        mb_xyxy = mb["xyxy"]

        if mb_id is None:
            return live_frame

        assoc_helmets    = [h  for h  in helmets    if is_overlapping(h["xyxy"],  mb_xyxy)]
        assoc_no_helmets = [nh for nh in no_helmets if is_overlapping(nh["xyxy"], mb_xyxy)]

        # --- Xe đã bị ghi nhận: chỉ vẽ màu xanh, bám theo ---
        if mb_id in self._captured_ids:
            draw_box(live_frame, mb_xyxy, f"motobike ID:{mb_id} (Captured)", COLOR_CAPTURED_VIOLATOR)
            for nh in assoc_no_helmets:
                draw_box(live_frame, nh["xyxy"], "No-Helmet", COLOR_CAPTURED_VIOLATOR)
            return live_frame

        # --- Xét vi phạm mới ---
        best_helmet_conf    = max((h["conf"]  for h  in assoc_helmets),    default=0.0)
        best_no_helmet_conf = max((nh["conf"] for nh in assoc_no_helmets), default=0.0)

        # ✅ Điều kiện vi phạm: no-helmet phải cao hơn helmet ít nhất VIOLATION_MARGIN
        is_violation = (
            best_no_helmet_conf > 0
            and (best_no_helmet_conf - best_helmet_conf) >= VIOLATION_MARGIN
        )

        if is_violation:
            self._captured_ids.add(mb_id)
            self.total_violators += 1

            # Vẽ đỏ lên live frame
            draw_box(live_frame, mb_xyxy, f"motobike ID:{mb_id}", COLOR_NEW_VIOLATOR)
            for nh in assoc_no_helmets:
                draw_box(live_frame, nh["xyxy"],
                         f"No-Helmet ({nh['conf']:.2f})", COLOR_NEW_VIOLATOR)

            # Chuẩn bị ảnh annotated để lưu bằng chứng
            detail_frame = raw_frame.copy()
            draw_box(detail_frame, mb_xyxy, f"motobike ID:{mb_id}", COLOR_NEW_VIOLATOR)
            for nh in assoc_no_helmets:
                draw_box(detail_frame, nh["xyxy"],
                         f"No-Helmet ({nh['conf']:.2f})", COLOR_NEW_VIOLATOR)

            timestamp = _make_timestamp()

            # Lưu ảnh ĐỒNG BỘ — chờ ghi xong mới gọi callback
            # Lý do: nếu lưu bất đồng bộ, browser load ảnh trước khi file tồn tại → ảnh trắng
            # _save_pair chỉ tốn 5-30ms (ghi JPEG local), chỉ chạy khi có vi phạm → OK
            saved = _save_pair(
                raw_frame.copy(), detail_frame,
                int(mb_id), timestamp, self.save_dir,
            )

            # Lấy đường dẫn thực tế sau khi lưu xong
            # Nếu lưu thất bại (saved = {}), dùng đường dẫn tính trước làm fallback
            raw_path = saved.get(
                "raw",
                os.path.join(self.save_dir, f"{timestamp}_raw_ID{int(mb_id)}.jpg")
            )
            ann_path = saved.get(
                "annotated",
                os.path.join(self.save_dir, f"{timestamp}_annotated_ID{int(mb_id)}.jpg")
            )

            # Gọi callback — ảnh đã chắc chắn tồn tại trên disk lúc này
            if self.on_violation:
                try:
                    self.on_violation(
                        bike_id    = int(mb_id),
                        timestamp  = timestamp,
                        confidence = float(best_no_helmet_conf),
                        paths      = {"raw": raw_path, "annotated": ann_path},
                    )
                except Exception as e:
                    print(f"[Detector] Lỗi on_violation callback: {e}")

            print(f"[{timestamp}] Vi phạm mới: ID {int(mb_id)} | "
                  f"no-helmet={best_no_helmet_conf:.2f} | Tổng: {self.total_violators}")

        return live_frame

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    def shutdown(self):
        """Dọn dẹp tài nguyên — gọi khi ứng dụng tắt."""
        self._executor.shutdown(wait=True)
        print("[Detector] Đã dọn dẹp ThreadPoolExecutor.")


# ==========================================================
# CHẠY TRỰC TIẾP (standalone — để test không cần web)
# ==========================================================
if __name__ == "__main__":
    VIDEO_PATH = "giaothong_khongmu_1.mp4"
    MODEL_PATH = "best.pt"

    detector = HelmetViolationDetector(
        model_path=MODEL_PATH,
        save_dir="violations",
        conf=DEFAULT_CONF,
    )
    try:
        detector.process_video(VIDEO_PATH, display=True)
    finally:
        detector.shutdown()
