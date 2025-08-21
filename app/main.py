# app/main.py
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil

from .plannings.router import router as planning_router

app = FastAPI(
    title="CSI – Contrôle Sécurité",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Page d'accueil (UI)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
def health():
    return {"status": "ok", "service": "csi-api", "docs": "/docs"}

# Optionnel : petit endpoint d’upload “neutre” (stocke en /tmp pour la session)
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    MAX = 25 * 1024 * 1024
    if file.size and file.size > MAX:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (>25 Mo).")
    tmpdir = Path("/tmp/csi-uploads")
    tmpdir.mkdir(parents=True, exist_ok=True)
    dest = tmpdir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": file.filename, "size": dest.stat().st_size}

# Routes “plannings”
app.include_router(planning_router)

# Gestion erreurs génériques (facultatif)
@app.exception_handler(Exception)
async def unhandled_error_handler(_req: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

from fastapi.staticfiles import StaticFiles

# Monte les fichiers statiques (css, js, images)
app.mount("/static", StaticFiles(directory="static"), name="static")
