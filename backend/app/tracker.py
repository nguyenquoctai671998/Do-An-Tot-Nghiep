"""
Module quản lý Tracking ID và chống trùng lặp ghi nhận bằng chứng vi phạm.
Đảm bảo 1 đối tượng (track_id) chỉ chụp ảnh bằng chứng 1 lần duy nhất trong toàn bộ video.
"""

class ViolationTracker:
    def __init__(self, confidence_threshold=0.5):
        self.captured_track_ids = set()
        self.confidence_threshold = confidence_threshold

    def should_capture(self, track_id: int, confidence: float) -> bool:
        """
        Kiểm tra xem đối tượng (track_id) đã được chụp bằng chứng chưa và độ tin cậy có đạt ngưỡng không.
        """
        if track_id is None:
            return False
        
        if track_id in self.captured_track_ids:
            return False  # Đã chụp bằng chứng trước đó rồi -> Bỏ qua
        
        if confidence >= self.confidence_threshold:
            self.captured_track_ids.add(track_id)
            return True
            
        return False

    def reset(self):
        """Reset danh sách tracking id khi xử lý video mới."""
        self.captured_track_ids.clear()
