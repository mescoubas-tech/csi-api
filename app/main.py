# app/main.py
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.4")

# Chemins absolus depuis ce fichier (évite les soucis en prod)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & templates (montage conditionnel pour ne pas crasher si le dossier n'existe pas)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

# API
app.include_router(planning_router)

# Healthcheck
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# Page d’accueil (UI)
@app.get("/", include_in_schema=False)
async def home(request: Request):
    index_path = TEMPLATES_DIR / "index.html"
    if templates and index_path.exists():
        return templates.TemplateResponse("index.html", {"request": request})
    # Fallback lisible si le template manque (évite le 500)
    return HTMLResponse(
        """
        <!do
