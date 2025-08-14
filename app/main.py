# app/main.py
from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

# Routers existants (imports RELATIFS car on est dans le package "app")
from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router

# (optionnels)
try:
    from .routers.schedules import router as schedules_router
except Exception:
    schedules_router = None

try:
    from .routers.ui import router as ui_router
except Exception:
    ui_router = None

# Nouveaux endpoints d'analyse
from .routes_analyze_latest import router as analyze_latest_router
from .routes_analyze_folder import router as analyze_folder_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
