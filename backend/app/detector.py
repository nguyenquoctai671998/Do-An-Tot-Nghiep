import os
import cv2
import time
from typing import List, Dict, Any
from tracker import ViolationTracker

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

class HelmetViolationDetector:
    def __init__(self, model_path: str = "weights/best.pt", confidence_threshold: float = 0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.tracker = ViolationTracker(confidence_threshold=confidence_threshold)
        self.model = None

    def load_model(self):
        """Khởi tạo mô hình YOLO từ file weights (.pt)."""
        if YOLO is None:
            raise ImportError("Vui lòng cài đặt ultralytics: pip install ultralytics")
        
        if os.path.exists(self.model_path):
            self.model = YOLO(self.model_path)
            print(f"✅ Đã tải thành công mô hình từ: {self.model_path}")
        else:
            # Fallback dùng yolov8n.pt nếu chưa có file custom best.pt
            print(f"⚠️ Không tìm thấy weights tại {self.model_path}. Dùng mô hình mặc định yolov8n.pt...")
            self.model = YOLO("yolov8n.pt")

    def process_video(self, video_path: str, output_dir: str) -> List[Dict[str, Any]]:
        """
        Xử lý video giao thông, nhận diện và chụp bằng chứng vi phạm.
        - output_dir/full/: Lưu ảnh toàn cảnh.
        - output_dir/crops/: Lưu ảnh cắt đối tượng vi phạm.
        """
        if self.model is None:
            self.load_model()

        self.tracker.reset()
        
        full_dir = os.path.join(output_dir, "full")
        crops_dir = os.path.join(output_dir, "crops")
        os.makedirs(full_dir, exist_ok=True)
        os.makedirs(crops_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Không thể mở file video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        violations = []
        frame_idx = 0

        # Chạy YOLO Tracking trên từng frame với ByteTrack
        results = self.model.track(source=video_path, stream=True, tracker="bytetrack.yaml")

        for r in results:
            frame = r.orig_img
            if frame is None:
                continue

            frame_idx += 1
            timestamp_sec = frame_idx / fps
            timestamp_str = time.strftime('%H:%M:%S', time.gmtime(timestamp_sec))

            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for box in boxes:
                # Lấy thông tin lớp nhận diện, độ tin cậy và track_id
                cls_id = int(box.cls[0].item())
                cls_name = self.model.names.get(cls_id, str(cls_id))
                conf = float(box.conf[0].item())
                
                track_id = int(box.id[0].item()) if box.id is not None else None

                # Kiểm tra nhãn vi phạm (ví dụ: 'without_helmet' hoặc class index quy định)
                is_violation = (cls_name.lower() in ["without_helmet", "no-helmet", "no_helmet"]) or (cls_id == 0)

                if is_violation and self.tracker.should_capture(track_id, conf):
                    # Tọa độ bounding box (x1, y1, x2, y2)
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = xyxy

                    # Mở rộng nhẹ lề crop để nhìn rõ đối tượng
                    h, w, _ = frame.shape
                    pad_x = int((x2 - x1) * 0.15)
                    pad_y = int((y2 - y1) * 0.15)
                    
                    crop_x1 = max(0, x1 - pad_x)
                    crop_y1 = max(0, y1 - pad_y)
                    crop_x2 = min(w, x2 + pad_x)
                    crop_y2 = min(h, y2 + pad_y)

                    crop_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]

                    # Tạo ảnh toàn cảnh có vẽ Bounding Box nổi bật
                    annotated_full_frame = frame.copy()
                    cv2.rectangle(annotated_full_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    cv2.putText(
                        annotated_full_frame, 
                        f"VIOLATION #{track_id} ({conf*100:.1f}%)", 
                        (x1, max(30, y1 - 10)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.8, (0, 0, 255), 2
                    )

                    # Lưu ảnh ra đĩa
                    filename = f"violation_id{track_id}_frame{frame_idx}"
                    full_path = os.path.join(full_dir, f"{filename}_full.jpg")
                    crop_path = os.path.join(crops_dir, f"{filename}_crop.jpg")

                    cv2.imwrite(full_path, annotated_full_frame)
                    cv2.imwrite(crop_path, crop_img)

                    # Lưu thông tin vi phạm
                    violation_record = {
                        "violation_id": len(violations) + 1,
                        "track_id": track_id,
                        "timestamp": timestamp_str,
                        "frame_index": frame_idx,
                        "confidence": round(conf * 100, 2),
                        "class_name": cls_name,
                        "full_image_path": full_path,
                        "crop_image_path": crop_path,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)]
                    }
                    violations.append(violation_record)
                    print(f"📸 [MỚI] Đã bắt vi phạm đối tượng #{track_id} tại {timestamp_str} (Độ tin cậy: {conf*100:.1f}%)")

        cap.release()
        return violations
