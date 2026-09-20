from ultralytics import YOLO

# Tải mô hình YOLOv8n
model = YOLO('best.pt')

# Xuất sang định dạng ONNX
model.export(format='onnx')