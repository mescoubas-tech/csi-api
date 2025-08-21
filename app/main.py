from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="CSI API", docs_url="/docs", redoc_url="/redoc")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index_old.html", {"request": request})

@app.get("/status")
def status():
    return {"status": "ok", "service": "csi-api", "docs": "/docs"}

from .plannings.router import router as planning_router
app.include_router(planning_router)
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import plannings as plannings_router

app = FastAPI(title="CSI API", version="1.5.0")

# CORS si ton front est séparé
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(plannings_router.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
