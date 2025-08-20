# app/main.py
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Response, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from pydantic import BaseModel
from .plannings.router import router as planning_router

# ──────────────────────────────────────────────────────────────────────────────
# Imports des routeurs EXISTANTS (relatifs car on est dans le package "app")
# ──────────────────────────────────────────────────────────────────────────────
from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router

# Optionnels : certains projets n'ont pas ces modules en dev
try:
    from .routers.schedules import router as schedules_router  # type: ignore
except Exception:
    schedules_router = None  # type: ignore

try:
    from .routers.ui import router as ui_router  # type: ignore
except Exception:
    ui_router = None  # type: ignore

# ──────────────────────────────────────────────────────────────────────────────
# App & configuration de base
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Analyse de conformité CNAPS",
    description="API d'analyse du Livre 6 du CSI",
    version="1.0.0",
)

# CORS large pour faciliter les tests depuis ton front (à restreindre plus tard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fichiers statiques et page d'accueil
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)


# ──────────────────────────────────────────────────────────────────────────────
# Montage des routeurs EXISTANTS
# ──────────────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
app.include_router(upload_router)

if schedules_router:
    app.include_router(schedules_router)  # type: ignore
if ui_router:
    app.include_router(ui_router)  # type: ignore

# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS D'ANALYSE INTÉGRÉS (pour éviter les erreurs de module manquant)
# ──────────────────────────────────────────────────────────────────────────────
import os
import re

# Base de stockage des uploads :
# - par défaut: "data/uploads" (=> /opt/render/project/src/data/uploads)
# - peut être sur un disque Render : set env UPLOAD_BASE=/var/data/uploads
UPLOAD_BASE = os.getenv("UPLOAD_BASE", "data/uploads")
_PLANNING_RE = re.compile(r"(planning|plannings|rota|schedule)", re.I)


def _uploads_dir() -> Path:
    """Renvoie le dossier base des uploads (absolu)."""
    base = Path(UPLOAD_BASE)
    return base if base.is_absolute() else (Path.cwd() / base)


@app.get("/analyze-latest", tags=["analyze"])
def analyze_latest(company: str = Query(..., min_length=1)):
    """
    Analyse le DERNIER dossier d'upload pour une société donnée.
    Dossiers attendus: <company>_YYYYmmdd_HHMMSS
    """
    base = _uploads_dir()
    if not base.exists():
        raise HTTPException(404, f"Upload base not found: {base}")

    dirs = sorted(
        [d for d in base.glob(f"{company}_*") if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        raise HTTPException(404, f"Aucun upload trouvé pour '{company}'")

    folder = dirs[0]
    pdfs = list(folder.rglob("*.pdf"))

    plannings = [str(p) for p in pdfs if _PLANNING_RE.search(p.name)]
    autres = [str(p) for p in pdfs if str(p) not in plannings]

    return {
        "message": "OK" if pdfs else "Aucune pièce détectée",
        "company": company,
        "folder": str(folder),
        "total_pdfs": len(pdfs),
        "plannings_detectes": plannings,
        "pieces_detectees": autres,
    }


class AnalyzeFolderIn(BaseModel):
    upload_folder: str


@app.post("/analyze-by-folder", tags=["analyze"])
def analyze_by_folder(inp: AnalyzeFolderIn):
    """
    Analyse directement un dossier exact renvoyé par /upload (champ 'upload_folder').
    """
    folder = Path(inp.upload_folder)
    if not folder.exists():
        raise HTTPException(404, f"Dossier introuvable: {folder}")

    pdfs = list(folder.rglob("*.pdf"))
    plannings = [str(p) for p in pdfs if _PLANNING_RE.search(p.name)]
    autres = [str(p) for p in pdfs if str(p) not in plannings]

    return {
        "message": "OK" if pdfs else "Aucune pièce détectée",
        "folder": str(folder),
        "total_pdfs": len(pdfs),
        "plannings_detectes": plannings,
        "pieces_detectees": autres,
    }
