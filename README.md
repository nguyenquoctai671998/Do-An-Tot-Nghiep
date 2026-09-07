# 🛵 Traffic Helmet Violation Detection & Management System
> **Hệ thống Giám sát & Quản lý Tự động Phát hiện Vi phạm Không đội Mũ bảo hiểm**

Hệ thống ứng dụng mô hình thị giác máy tính **YOLOv8** kết hợp thuật toán theo dõi đa đối tượng **ByteTrack** và nền tảng web sử dụng **FastAPI + WebSocket** để giám sát, ghi nhận và quản lý hồ sơ vi phạm giao thông.

---

## 📌 Tính Năng Nổi Bật

* **Phát hiện đối tượng xe máy, đội mũ, không mũ:** Nhận diện phương tiện xe máy (`motobike`), người đội mũ (`helmet`) và không đội mũ bảo hiểm (`no-helmet`).
* **Theo dõi & Chống bắt trùng (Anti-Duplicate):** Tích hợp ByteTrack gán ID cho từng xe, tự động vẽ bám theo xe đã ghi nhận và không tạo vi phạm trùng lặp.
* **Stream Video qua WebSocket:** Truyền tải luồng video trực tiếp từ backend AI xuống trình duyệt web mượt mà, không giật lag.
* **Ghi nhận Bằng chứng Kép:** Tự động lưu 2 ảnh bằng chứng độ phân giải cao cho mỗi vi phạm (ảnh gốc + ảnh khoanh vùng vi phạm đỏ).
* **Giao diện Dashboard:**
  * Lọc vi phạm theo trạng thái: **Chờ duyệt**, **Đã xác nhận**, **Đã hủy**.
  * Duyệt nhanh vi phạm trực tiếp ngay trong lúc xem video hoặc trên Dashboard.
  * Tìm kiếm tức thời theo ID xe, mã vi phạm hoặc tên file video.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
helmet_violation_system/
├── detection/
│   ├── __init__.py
│   └── detector.py            # Lõi xử lý AI (YOLOv8 + ByteTrack + Lưu ảnh)
├── web/
│   ├── __init__.py
│   ├── main.py                # Điểm khởi động FastAPI App & router
│   ├── models.py              # Định nghĩa Data models (Violation, Stats)
│   ├── database.py            # Quản lý cơ sở dữ liệu SQLite
│   ├── job_manager.py         # Quản lý hàng đợi video stream & tác vụ ngầm
│   └── routers/
│       ├── __init__.py
│       ├── upload.py          # API upload video & worker thread
│       ├── stream.py          # WebSocket stream video + sự kiện vi phạm
│       └── violations.py      # CRUD APIs & phục vụ ảnh bằng chứng
├── templates/
│   ├── base.html              # Template giao diện chung (Bootstrap 5)
│   ├── index.html             # Trang tải lên video (Upload page)
│   ├── view.html              # Trang theo dõi video & duyệt vi phạm trực tiếp
│   └── dashboard.html         # Trang bảng điều khiển quản lý hồ sơ vi phạm
├── static/
│   └── js/
│       └── app.js             # Logic Frontend tương tác API & WebSocket
├── best.pt                    # File trọng số mô hình YOLOv8 đã train
├── requirements.txt           # Danh sách thư viện Python cần thiết
├── database.db                # Cơ sở dữ liệu SQLite (tự tạo khi chạy)
├── uploads/                   # Thư mục lưu video tải lên (tự tạo)
└── violations/                # Thư mục lưu ảnh chụp bằng chứng (tự tạo)
```

---

## 🛠️ Hướng Dẫn Cài Đặt Môi Trường

### 1. Các bước cài đặt chi tiết

#### **Bước 1: Mở Terminal và di chuyển vào thư mục dự án**
```bash
cd /Users/nguyenquoctai6798/helmet_violation_system
```

#### **Bước 2: Cài đặt các thư viện cần thiết**
Cài đặt toàn bộ gói phụ thuộc từ `requirements.txt`:
```bash
pip install -r requirements.txt
```

*Hoặc cài đặt thủ công*
```bash
pip install fastapi "uvicorn[standard]" python-multipart jinja2 ultralytics opencv-python
```

---

## Hướng Dẫn Khởi Chạy Hệ Thống

### 1. Khởi động Web Server
Chạy lệnh sau tại thư mục gốc của dự án:

```bash
python3 -m uvicorn web.main:app --reload --host 0.0.0.0 --port 8000
```


### 2. Truy cập ứng dụng trên Trình duyệt

| Trang chức năng | Đường dẫn URL | Mô tả |
|---|---|---|
| **Trang chủ (Upload Video)** | [http://localhost:8000/] | Kéo thả video giao thông để bắt đầu phân tích |
| **Bảng Điều Khiển (Dashboard)** | [http://localhost:8000/dashboard] | Xem, lọc, tìm kiếm, duyệt và xóa hồ sơ vi phạm |
| **Tài liệu API (Swagger UI)** | [http://localhost:8000/docs] | Kiểm tra và gọi thử toàn bộ RESTful APIs |

---

### 3. Cách sử dụng nhanh
1. Mở trình duyệt vào [http://localhost:8000/].
2. Kéo thả hoặc chọn một file video giao thông (`.mp4`, `.avi`, `.mov`).
3. Bấm **"Bắt Đầu Phân Tích"** -> Hệ thống tự động chuyển sang trang xem trực tiếp.
4. Video được stream ở khung bên trái; khi có vi phạm, thẻ vi phạm kèm ảnh bằng chứng sẽ tự động nhảy ra ở khung bên phải.
5. Bạn có thể bấm **"Xác Nhận"** hoặc **"Hủy Bỏ"** trực tiếp trên thẻ vi phạm mà không làm gián đoạn video.
6. Vào trang **Dashboard** để lọc theo trạng thái, tìm kiếm ID xe hoặc dọn dẹp dữ liệu khi cần.

