import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from web.database import init_db
from web.routers import upload, stream, violations

# ==========================================================
# KHOI TAO APP
# ==========================================================

app = FastAPI(
    title="Helmet Violation Detection System",
    description="He thong nhan dien vi pham khong doi mu bao hiem",
    version="1.0.0",
)

# Thu muc goc cua project (1 cap tren thu muc web/)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Phuc vu file tinh (CSS, JS, anh)
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)

# Template HTML (Jinja2)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ==========================================================
# STARTUP EVENT — Chay 1 lan khi app khoi dong
# ==========================================================

@app.on_event("startup")
async def startup_event():
    """
    Chay truoc khi app bat dau nhan request.
    Dam bao database.db va cac thu muc can thiet ton tai.
    """
    init_db()

    # Tao thu muc luu anh va video neu chua co
    for folder in ["violations", "uploads"]:
        path = os.path.join(BASE_DIR, folder)
        os.makedirs(path, exist_ok=True)

    print("[App] He thong da san sang.")
    print("[App] Mo browser tai: http://localhost:8000")


# ==========================================================
# INCLUDE ROUTERS
# ==========================================================

app.include_router(upload.router)      # /upload, /job/{id}
app.include_router(stream.router)      # /ws/{job_id}
app.include_router(violations.router)  # /api/violations, /api/stats, /api/images


# ==========================================================
# PAGE ROUTES — Tra ve HTML
# ==========================================================

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """
    GET / — Trang chu: upload video va xem live.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """
    GET /dashboard — Trang quan ly vi pham.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/view/{job_id}", response_class=HTMLResponse)
async def view_page(request: Request, job_id: str):
    """
    GET /view/{job_id} — Trang xem video dang xu ly theo job_id.
    """
    return templates.TemplateResponse(
        "view.html",
        {"request": request, "job_id": job_id}
    )
