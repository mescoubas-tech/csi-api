from __future__ import annotations
import os, io, re
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse

# ==================== Version ====================
VERSION = "CNAPS-UI-3.1"

app = FastAPI(title="CSI API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ==================== Dossiers ====================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Gestion sécurisée de "exports"
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

# Dossier CNAPS (pour les uploads)
CNAPS_DIR = (PROJECT_ROOT / "uploads" / "cnaps").resolve()
CNAPS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Docs CNAPS ====================
DOCS: List[Dict] = [
    {"key":"autorisation_exercer", "label":"Autorisation d’exercer", "ext":["pdf","doc","docx"]},
    {"key":"agrement_dirigeant", "label":"Agrément dirigeant", "ext":["pdf","doc","docx"]},
    {"key":"attestation_assurance", "label":"Attestation d’assurance professionnelle", "ext":["pdf"]},
    {"key":"kbis", "label":"Extrait Kbis", "ext":["pdf"]},
    {"key":"statuts_maj", "label":"Statuts de l’entreprise à jour", "ext":["pdf"]},
    {"key":"dsn", "label":"Déclarations sociales nominatives (DSN)", "ext":["zip","pdf"]},
    {"key":"vigilance_urssaf", "label":"Attestation de vigilance URSSAF", "ext":["pdf"]},
    {"key":"releves_comptes_6m", "label":"Relevés de comptes (6 mois)", "ext":["pdf","csv"]},
    {"key":"derniere_liasse", "label":"Dernière liasse fiscale", "ext":["pdf","zip"]},
    {"key":"grand_livre", "label":"Grand livre de comptes", "ext":["pdf","csv","xls","xlsx"]},
]

ALLOWED_SUFFIXES = {f".{e.lower()}" for d in DOCS for e in d["ext"]}
MAX_BYTES = 25 * 1024 * 1024  # 25 Mo

# ==================== HEALTH & DEBUG ====================
@app.get("/health", include_in_schema=False)
async def health():
    return {"status":"ok", "version": VERSION, "cnaps_dir": str(CNAPS_DIR), "exports_dir": str(EXPORTS_DIR)}

@app.get("/__debug", include_in_schema=False)
async def debug():
    return {
        "version": VERSION,
        "cwd": os.getcwd(),
        "cnaps_dir": str(CNAPS_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "files_exports": [p.as_posix() for p in EXPORTS_DIR.rglob("*") if p.is_file()],
    }

# ==================== PAGE D’ACCUEIL ====================
@app.get("/", include_in_schema=False)
async def home():
    html = f"""
    <!doctype html><meta charset='utf-8'>
    <title>CSI • Accueil</title>
    <meta name='viewport' content='width=device-width,initial-scale=1'>
    <style>
      body{{margin:0;background:#0b1020;color:#e6e9f2;font:16px/1.6 system-ui}}
      .wrap{{max-width:980px;margin:48px auto;padding:0 20px}}
      .card{{background:#111833;border:1px solid #1b254a;border-radius:16px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.3)}}
      a{{color:#6aa1ff;text-decoration:none}}
      .pill{{display:inline-block;margin:8px 8px 0 0;padding:10px 14px;border-radius:10px;border:1px solid #2a3a75;background:#1a2a6a}}
      .muted{{color:#9aa3b2}}
    </style>
    <div class='wrap'><div class='card'>
      <h1>CSI API</h1>
      <p>
        <a class='pill' href='/cnaps'>🧾 Analyse de conformité CNAPS</a>
        <a class='pill' href='/docs' target='_blank'>📘 Docs API</a>
        <a class='pill' href='/health' target='_blank'>🩺 Health</a>
      </p>
      <p class='muted'>Version : {VERSION}</p>
    </div></div>
    """
    return HTMLResponse(html)

# ==================== PAGE CNAPS (UI) ====================
@app.get("/cnaps", include_in_schema=False)
async def cnaps_page():
    import json
    docs_json = json.dumps(DOCS)
    html = f"""
    <!doctype html><meta charset="utf-8">
    <title>Analyse de conformité CNAPS — Téléversement</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <body style="font-family:system-ui;background:#0b1020;color:#e6e9f2;margin:0">
      <div style="max-width:1200px;margin:40px auto;padding:0 20px">
        <h1>Analyse de conformité CNAPS — Téléversement</h1>
        <div><a href="/">Accueil</a> · <a href="/docs">Docs</a></div>
        <div id="cards"></div>
        <h2>Nomenclature des pièces</h2>
        <ul id="nomenclature"></ul>
      </div>
      <script>
        const DOCS = {docs_json};
        async function refresh(){{
          const r = await fetch('/cnaps/list'); const j = await r.json();
          const cards = document.getElementById('cards'); cards.innerHTML='';
          DOCS.forEach(d=>{{
            const files = j.data[d.key]||[];
            cards.insertAdjacentHTML('beforeend', `<div style='border:1px solid #2a3a75;margin:8px;padding:8px;border-radius:8px'>
              <b>${{d.label}}</b> (${{d.ext.join('/')}}) ${{files.length>0?"✓":""}}<br>
              ${{files.map(f=>`<a href='/cnaps/file/${{d.key}}/${{f.name}}' target='_blank'>${{f.name}}</a> (${f.size_fmt})`).join('<br>')||"<i>aucun</i>"}}
              <form onsubmit='return upload(this,"${{d.key}}")'>
                <input type=file name=file><button>Uploader</button>
              </form>
            </div>`);
          }});
          document.getElementById('nomenclature').innerHTML = DOCS.map(d=>`<li>${{d.label}}</li>`).join('');
        }}
        async function upload(form,kind){{
          const fd=new FormData(form); fd.append('kind',kind);
          const r=await fetch('/cnaps/upload',{method:'POST',body:fd});
          if(r.ok) refresh(); else alert('Erreur upload');
          return false;
        }}
        refresh();
      </script>
    </body>
    """
    return HTMLResponse(html)

# ==================== API CNAPS ====================
def _safe_filename(name: str) -> str:
    name = name.strip().replace("\x00", "")
    name = re.sub(r"[^\w\.-]+", "_", name)
    return name[:180] or "fichier"

def _kind_dir(kind: str) -> Path:
    d = CNAPS_DIR / kind
    d.mkdir(parents=True, exist_ok=True)
    return d

@app.get("/cnaps/list")
async def cnaps_list():
    data: Dict[str, List[Dict]] = {}
    for d in DOCS:
        k = d["key"]; dirp = _kind_dir(k)
        items = []
        for p in sorted(dirp.iterdir()):
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                st = p.stat()
                size_fmt = f"{st.st_size/1024:.1f} Ko" if st.st_size<1024**2 else f"{st.st_size/1024**2:.1f} Mo"
                items.append({"name":p.name,"size":st.st_size,"size_fmt":size_fmt,"mtime":int(st.st_mtime)})
        data[k] = items
    return {"ok": True, "data": data}

@app.post("/cnaps/upload")
async def cnaps_upload(kind: str = Form(...), file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_SUFFIXES:
        raise HTTPException(400,"Extension non autorisée")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413,"Fichier trop volumineux")
    path = _kind_dir(kind) / _safe_filename(file.filename)
    with open(path,"wb") as f: f.write(content)
    return {"ok": True, "name": path.name}

@app.get("/cnaps/file/{kind}/{name}")
async def cnaps_file(kind:str, name:str):
    path = _kind_dir(kind) / name
    if not path.is_file(): raise HTTPException(404)
    return FileResponse(path, filename=path.name)

@app.delete("/cnaps/file/{kind}/{name}")
async def cnaps_del(kind:str,name:str):
    path = _kind_dir(kind) / name
    if not path.is_file(): raise HTTPException(404)
    path.unlink(); return {"ok":True}
