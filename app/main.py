from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Répertoires (robuste, quel que soit l'endroit d'exécution) ---
BASE_DIR = Path(__file__).resolve().parent      # app/
STATIC_DIR = BASE_DIR / "static"                # app/static
TEMPLATES_DIR = BASE_DIR / "templates"          # app/templates

# --- Application ---
app = FastAPI(
    title="CSI API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Fichiers statiques & templates ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- Page d'accueil : interface “ancienne” ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Assure-toi que app/templates/index_old.html existe
    return templates.TemplateResponse("index_old.html", {"request": request})

# --- Health/Status simple (pour monitoring/render) ---
@app.get("/status")
def status():
    return {"status": "ok", "service": "csi-api", "docs": "/docs"}

# --- Routes Planning (analyse/export/health) ---
# Assure-toi que app/plannings/router.py existe et définit `router`
try:
    from .plannings.router import router as planning_router
    app.include_router(planning_router)
except Exception as e:
    # On ne crash pas l'app si le module planning est manquant, mais on log l'erreur.
    # Render affichera l'exception dans les logs au démarrage si besoin.
    import logging
    logging.getLogger("uvicorn.error").error("Impossible de monter le routeur 'planning': %s", e)
