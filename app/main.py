from __future__ import annotations
import os, io, re, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# ==================== Version ====================
VERSION = "UI-Blanche-onglets-1.0"

# ==================== App ====================
app = FastAPI(title="CSI API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ==================== Dossiers ====================
BASE_DIR = Path(__file__).resolve().parent      # app/
PROJECT_ROOT = BASE_DIR.parent                  # repo root

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def ensure_exports_dir() -> Path:
    wanted = (PROJECT_ROOT / "exports").resolve()
    try:
        wanted.mkdir(parents=True, exist_ok=True)
        if not wanted.is_dir():
            raise NotADirectoryError(str(wanted))
        return wanted
    except (FileExistsError, NotADirectoryError):
        alt = (PROJECT_ROOT / "exports_data").resolve()
        alt.mkdir(parents=True, exist_ok=True)
        return alt

EXPORTS_DIR = ensure_exports_dir()
CNAPS_DIR = (PROJECT_ROOT / "uploads" / "cnaps").resolve()
CNAPS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Spéc CNAPS ====================
DOCS: List[Dict] = [
    {"key": "autorisation_exercer", "label": "Autorisation d’exercer", "ext": ["pdf", "doc", "docx"]},
    {"key": "agrement_dirigeant", "label": "Agrément dirigeant", "ext": ["pdf", "doc", "docx"]},
    {"key": "attestation_assurance", "label": "Attestation d’assurance professionnelle", "ext": ["pdf"]},
    {"key": "kbis", "label": "Extrait Kbis", "ext": ["pdf"]},
    {"key": "statuts_maj", "label": "Statuts de l’entreprise à jour", "ext": ["pdf"]},
    {"key": "dsn", "label": "Déclarations sociales nominatives (DSN)", "ext": ["zip", "pdf"]},
    {"key": "vigilance_urssaf", "label": "Attestation de vigilance URSSAF", "ext": ["pdf"]},
    {"key": "releves_comptes_6m", "label": "Relevés de comptes (6 mois)", "ext": ["pdf", "csv"]},
    {"key": "derniere_liasse", "label": "Dernière liasse fiscale", "ext": ["pdf", "zip"]},
    {"key": "grand_livre", "label": "Grand livre de comptes", "ext": ["pdf", "csv", "xls", "xlsx"]},
]
ALLOWED_SUFFIXES = {f".{e.lower()}" for d in DOCS for e in d["ext"]}
MAX_BYTES = 25 * 1024 * 1024  # 25 Mo

# ==================== Option : routeur planning existant ====================
try:
    from app.plannings.router import router as planning_router
    app.include_router(planning_router)
except Exception:
    pass

# ==================== Utils ====================
def _safe_filename(name: str) -> str:
    name = name.strip().replace("\x00", "")
    name = re.sub(r"[^\w\.-]+", "_", name, flags=re.U)
    return name[:180] or "fichier"

def _kind_dir(kind: str) -> Path:
    d = (CNAPS_DIR / kind).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d

def _human_size(n: int) -> str:
    if n < 1024: return f"{n} o"
    if n < 1024**2: return f"{n/1024:.1f} Ko"
    if n < 1024**3: return f"{n/1024**2:.1f} Mo"
    return f"{n/1024**3:.2f} Go"

# ==================== Health & Debug ====================
@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "ok",
        "version": VERSION,
        "templates": str(TEMPLATES_DIR),
        "static": str(STATIC_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "cnaps_dir": str(CNAPS_DIR),
    }

@app.get("/__debug", include_in_schema=False)
async def debug():
    return {
        "version": VERSION,
        "cwd": os.getcwd(),
        "ls_templates": sorted(p.name for p in TEMPLATES_DIR.glob("*.html")),
        "ls_static": sorted(p.name for p in STATIC_DIR.glob("*")),
        "exports": sorted(p.name for p in EXPORTS_DIR.glob("*")),
    }

# ==================== PAGES (templates Jinja) ====================
@app.get("/", include_in_schema=False)
async def home(request: Request):
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "version": VERSION})

@app.get("/analyse-planning", include_in_schema=False)
async def analyse_planning_page(request: Request):
    return TEMPLATES.TemplateResponse("analyse_planning.html", {"request": request, "version": VERSION})

@app.get("/cnaps", include_in_schema=False)
async def cnaps_page(request: Request):
    # On passe DOCS au template (affichage + JS)
    return TEMPLATES.TemplateResponse("cnaps.html", {"request": request, "version": VERSION, "DOCS": DOCS})

@app.get("/telechargements", include_in_schema=False)
async def telechargements_page(request: Request):
    return TEMPLATES.TemplateResponse("telechargements.html", {"request": request, "version": VERSION})

# ==================== API CNAPS ====================
@app.get("/cnaps/list")
async def cnaps_list():
    data: Dict[str, List[Dict]] = {}
    for d in DOCS:
        k = d["key"]
        dirp = _kind_dir(k)
        items = []
        for p in sorted(dirp.iterdir()):
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                st = p.stat()
                items.append({
                    "name": p.name,
                    "size": st.st_size,
                    "size_fmt": _human_size(st.st_size),
                    "mtime": int(st.st_mtime),
                    "mtime_h": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        data[k] = items
    return {"ok": True, "data": data}

@app.post("/cnaps/upload")
async def cnaps_upload(kind: str = Form(...), file: UploadFile = File(...)):
    if kind not in {d["key"] for d in DOCS}:
        raise HTTPException(400, "Type de pièce inconnu.")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Extension non autorisée: {ext}")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Fichier trop volumineux (max 25 Mo).")
    path = _kind_dir(kind) / _safe_filename(file.filename)
    with open(path, "wb") as f:
        f.write(content)
    return {"ok": True, "name": path.name}

@app.get("/cnaps/file/{kind}/{name}")
async def cnaps_get(kind: str, name: str):
    path = _kind_dir(kind) / name
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, filename=path.name)

@app.delete("/cnaps/file/{kind}/{name}")
async def cnaps_del(kind: str, name: str):
    path = _kind_dir(kind) / name
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    path.unlink()
    return {"ok": True}

# ==================== API Téléchargements (exports) ====================
@app.get("/downloads/list")
async def list_downloads():
    if not EXPORTS_DIR.exists():
        return {"files": []}
    items = []
    for p in sorted(EXPORTS_DIR.iterdir()):
        if p.is_file():
            st = p.stat()
            items.append({
                "name": p.name,
                "size": st.st_size,
                "size_fmt": _human_size(st.st_size),
                "mtime": int(st.st_mtime),
                "mtime_h": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "url": f"/downloads/file/{p.name}",
            })
    return {"files": items}

@app.get("/downloads/file/{name}")
async def download_file(name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "Nom invalide.")
    path = EXPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, filename=path.name)

@app.get("/downloads/all.zip")
async def download_all_zip():
    files = [p for p in EXPORTS_DIR.iterdir() if p.is_file()]
    if not files:
        raise HTTPException(404, "Aucun fichier à zipper.")
    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=exports_tout.zip"})

from pydantic import BaseModel
class ZipSelection(BaseModel):
    names: List[str]

@app.post("/downloads/zip")
async def download_selection_zip(payload: ZipSelection):
    files = []
    seen = set()
    for name in payload.names:
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(400, f"Nom invalide: {name}")
        p = EXPORTS_DIR / name
        if not p.is_file():
            raise HTTPException(404, f"Introuvable: {name}")
        if name not in seen:
            files.append(p); seen.add(name)
    if not files:
        raise HTTPException(400, "Aucun fichier sélectionné.")
    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition":"attachment; filename=selection.zip"})
