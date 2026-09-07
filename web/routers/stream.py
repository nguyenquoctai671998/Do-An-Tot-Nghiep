"""
web/routers/stream.py — WebSocket endpoint truyền dữ liệu real-time.

Endpoint:
  WebSocket /ws/{job_id}

3 loại message server gửi xuống browser:
  {"type": "frame",     "data": "<base64 JPEG>"}    → cập nhật video
  {"type": "violation", "data": {id, bike_id, ...}}  → hiện card vi phạm
  {"type": "done",      "total": 5}                  → báo xong, đóng kết nối
  {"type": "error",     "message": "..."}            → lỗi nghiêm trọng

Thiết kế:
  - Vòng lặp đọc queue KHÔNG BLOCKING (get_nowait)
  - asyncio.sleep(0.01) nhường CPU khi queue rỗng
  - WebSocket chỉ đóng khi nhận "done" hoặc lỗi nghiêm trọng
  - Lỗi gửi frame đơn lẻ KHÔNG đóng WebSocket (bỏ qua frame đó)
"""

import asyncio
import queue as std_queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web import job_manager as jm

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def websocket_stream(websocket: WebSocket, job_id: str):
    """
    WebSocket /ws/{job_id} — Stream frame và vi phạm real-time về browser.
    """
    await websocket.accept()
    print(f"[WS] Ket noi moi | job_id={job_id}")

    # Kiểm tra job tồn tại
    job = jm.get_job(job_id)
    if not job:
        await websocket.send_json({
            "type"   : "error",
            "message": f"Khong tim thay job: {job_id}",
        })
        await websocket.close()
        return

    try:
        consecutive_errors = 0  # Đếm lỗi liên tiếp để phát hiện lỗi nghiêm trọng

        while True:
            try:
                # Lấy item từ queue không blocking
                item = job.data_queue.get_nowait()
                consecutive_errors = 0  # Reset khi lấy được item

                try:
                    # Gửi xuống browser
                    await websocket.send_json(item)
                except Exception as send_err:
                    # In rõ loại message và exception để dễ debug
                    msg_type = item.get("type", "unknown")
                    print(f"[WS] Loi gui message type='{msg_type}': {send_err}")
                    # Với frame ảnh: bỏ qua, không đóng kết nối
                    # Với violation: cũng bỏ qua frame này nhưng in cảnh báo rõ
                    if msg_type == "violation":
                        print(f"[WS] CANH BAO: Vi pham bi mat, kiem tra JSON serialization!")
                    continue

                # Chỉ đóng khi nhận tín hiệu kết thúc
                if item.get("type") in ("done", "error"):
                    print(f"[WS] Nhan tin hieu '{item.get('type')}' — dong ket noi.")
                    break

            except std_queue.Empty:
                # Queue rỗng — kiểm tra trạng thái job
                if job.status == jm.JOB_DONE:
                    # Job xong, queue đã được đọc hết
                    await websocket.send_json({
                        "type" : "done",
                        "total": job.total_violations,
                    })
                    break
                elif job.status == jm.JOB_ERROR:
                    # Job lỗi nghiêm trọng, queue đã đọc hết
                    await websocket.send_json({
                        "type"   : "error",
                        "message": job.error_message or "Loi xu ly video.",
                    })
                    break
                else:
                    # Job vẫn đang chạy, đợi thêm dữ liệu
                    await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        # Browser chủ động đóng tab hoặc mất kết nối mạng
        print(f"[WS] Browser ngat ket noi | job_id={job_id}")

    except Exception as e:
        print(f"[WS] Loi nghiem trong | job_id={job_id} | {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

    finally:
        print(f"[WS] Dong WebSocket | job_id={job_id} "
              f"| Tong vi pham: {job.total_violations}")
