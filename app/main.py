# app/main.py
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.5")

# chemins absolus robustes
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & templates
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

# API
app.include_router(planning_router)

# Health
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# Home (UI)
@app.get("/", include_in_schema=False)
async def home(request: Request):
    if templates and (TEMPLATES_DIR / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request})
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>CSI API</title>"
        "<style>body{font:16px/1.6 system-ui;padding:32px}</style>"
        "<h1>CSI API</h1>"
        "<p>UI non trouvée (app/templates/index.html absent).</p>"
        "<ul>"
        "<li>Vérifie que <code>app/templates/index.html</code> est commité.</li>"
