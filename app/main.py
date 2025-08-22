# app/main.py
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse

# --- VERSION visible dans /health pour vérifier le déploiement ---
VERSION = "CSI-Downloads-1.0"

app = FastAPI(title="CSI API", version=VERSION)

# CORS large (adapte si nécessaire)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === EXPORTS: répertoire où tu mets les dossiers/fichiers à télécharger ===
# Par défaut: <racine du projet>/exports  (tu peux changer via var d'env EXPORTS_DIR)
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
EXPORTS_DIR = Path(os.getenv("EXPORTS_DIR", PROJECT_ROOT / "exports")).resolve()
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Extensions autorisées (tu peux en ajouter)
ALLOWED_SUFFIXES = {".zip", ".csv", ".xlsx", ".xls", ".pdf", ".txt", ".json"}

# --- Ton routeur métier (analyse plannings), garde-le si existant ---
try:
    from app.plannings.router import router as planning_router
    app.include_router(planning_router)
except Exception:
    # Pas bloquant si l'API planings n'est pas prête
    pass

# ---------------------- HEALTH & DEBUG ----------------------
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": VERSION, "exports_dir": str(EXPORTS_DIR)}

@app.get("/__debug", include_in_schema=False)
async def debug():
    try:
        files = sorted(p.name for p in EXPORTS_DIR.glob("*"))
    except Exception as e:
        files = [f"<error: {e}>"]
    return {
        "version": VERSION,
        "cwd": os.getcwd(),
        "project_root": str(PROJECT_ROOT),
        "exports_dir": str(EXPORTS_DIR),
        "exports_list": files,
    }

# ---------------------- PAGE D'ACCUEIL ----------------------
@app.get("/", include_in_schema=False)
async def home():
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>CSI • Accueil</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='icon' href='data:,'>"
        "<style>"
        "body{margin:0;background:linear-gradient(180deg,#0b1020,#0e1630);color:#e6e9f2;"
        "font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial}"
        ".wrap{max-width:960px;margin:48px auto;padding:0 20px}"
        ".card{background:#111833;border:1px solid #1b254a;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.3);padding:24px}"
        "h1{margin:0 0 12px;font-size:28px} a{color:#6aa1ff;text-decoration:none}"
        ".links{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}"
        ".pill{display:inline-block;padding:10px 14px;border-radius:10px;border:1px solid #2a3a75;background:#1a2a6a}"
        "</style>"
        "<div class='wrap'><div class='card'>"
        "<h1>CSI API</h1>"
        "<div class='links'>"
        "<a class='pill' href='/telechargements'>📁 Téléchargements</a>"
        "<a class='pill' href='/analyse-planning'>🔎 Analyse planning</a>"
        "<a class='pill' href='/docs' target='_blank'>📘 Docs API</a>"
        "<a class='pill' href='/health' target='_blank'>🩺 Health</a>"
        "</div>"
        f"<p style='color:#9aa3b2;margin-top:10px'>Version: {VERSION}</p>"
        "</div></div>"
    )
    return HTMLResponse(html, status_code=200)

# ---------------------- UI: TÉLÉCHARGEMENTS ----------------------
@app.get("/telechargements", include_in_schema=False)
async def telechargements():
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>CSI • Téléchargements</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='icon' href='data:,'>"
        "<style>"
        "body{margin:0;background:linear-gradient(180deg,#0b1020,#0e1630);color:#e6e9f2;"
        "font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial}"
        ".wrap{max-width:1100px;margin:48px auto;padding:0 20px}"
        ".card{background:#111833;border:1px solid #1b254a;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.3);padding:24px}"
        "h1{margin:0 0 12px;font-size:28px} .muted{color:#9aa3b2}"
        ".row{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 18px}"
        "button{cursor:pointer;border:1px solid #2a3a75;background:#1a2a6a;color:#eaf1ff;padding:10px 14px;border-radius:10px}"
        "table{width:100%;border-collapse:collapse;margin-top:8px}"
        "th,td{border:1px solid #223166;padding:8px;text-align:left} th{background:#182455}"
        "input[type=checkbox]{transform:scale(1.2)}"
        "a{color:#6aa1ff;text-decoration:none}"
        "</style>"
        "<div class='wrap'><div class='card'>"
        "<h1>Tous les dossiers à télécharger</h1>"
        "<p class='muted'>Les fichiers sont pris dans le dossier <code>/exports</code> du projet.</p>"
        "<div class='row'>"
        "<button id='btn-refresh'>Rafraîchir</button>"
        "<a class='btn' href='/downloads/all.zip'>Télécharger tout (ZIP)</a>"
        "<button id='btn-zip-selected'>Télécharger la sélection (ZIP)</button>"
        "<a href='/' style='margin-left:auto'>← Accueil</a>"
        "</div>"
        "<div id='status' class='muted' style='margin-bottom:8px'>Chargement…</div>"
        "<div style='overflow:auto'>"
        "<table id='tbl'><thead><tr>"
        "<th><input type='checkbox' id='select-all'></th>"
        "<th>Nom</th><th>Taille</th><th>Modifié</th><th>Télécharger</th>"
        "</tr></thead><tbody></tbody></table>"
        "</div>"
        "</div></div>"
        "<script>"
        "const tbl = document.querySelector('#tbl tbody');"
        "const statusEl = document.getElementById('status');"
        "async function sizeFmt(b){if(b<1024)return b+' o';if(b<1024*1024)return (b/1024).toFixed(1)+' Ko';if(b<1024*1024*1024)return (b/1024/1024).toFixed(1)+' Mo';return (b/1024/1024/1024).toFixed(2)+' Go';}"
        "async function load(){"
        "  statusEl.textContent='Chargement…';"
        "  tbl.innerHTML='';"
        "  try{"
        "    const r = await fetch('/downloads/list');"
        "    const j = await r.json();"
        "    if(!r.ok){throw new Error(j.detail||'Erreur de liste');}"
        "    const rows = j.files||[];"
        "    if(rows.length===0){statusEl.textContent='Aucun fichier trouvé.';return;}"
        "    statusEl.textContent = rows.length+' fichier(s)';"
        "    rows.forEach(f=>{"
        "      const tr=document.createElement('tr');"
        "      tr.innerHTML="
        "        `<td><input type='checkbox' class='sel' data-name='${f.name}'></td>`+"
        "        `<td>${f.name}</td>`+"
        "        `<td>${f.size_fmt}</td>`+"
        "        `<td>${f.mtime_h}</td>`+"
        "        `<td><a href='/downloads/file/${encodeURIComponent(f.name)}'>Télécharger</a></td>`;"
        "      tbl.appendChild(tr);"
        "    });"
        "  }catch(e){ statusEl.textContent='Erreur: '+(e.message||e); }"
        "}"
        "document.getElementById('btn-refresh').addEventListener('click', load);"
        "document.getElementById('select-all').addEventListener('change', e=>{"
        "  document.querySelectorAll('input.sel').forEach(cb=>cb.checked=e.target.checked);"
        "});"
        "document.getElementById('btn-zip-selected').addEventListener('click', async ()=>{"
        "  const names=[...document.querySelectorAll('input.sel:checked')].map(cb=>cb.dataset.name);"
        "  if(names.length===0){alert('Sélectionne au moins un fichier.');return;}"
        "  try{"
        "    const r = await fetch('/downloads/zip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({names})});"
        "    if(!r.ok){const j=await r.json().catch(()=>({detail:'Erreur'}));throw new Error(j.detail||'Erreur zip');}"
        "    const blob = await r.blob();"
        "    const url = URL.createObjectURL(blob);"
        "    const a = document.createElement('a'); a.href=url; a.download='selection.zip'; a.click();"
        "    URL.revokeObjectURL(url);"
        "  }catch(e){ alert(e.message||e); }"
        "});"
        "load();"
        "</script>"
    )
    return HTMLResponse(html, status_code=200)

# ---------------------- UI: ANALYSE (optionnel) ----------------------
@app.get("/analyse-planning", include_in_schema=False)
async def analyse_planning_page():
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Analyse planning</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='icon' href='data:,'>"
        "<style>body{margin:0;background:#0b1020;color:#e6e9f2;font:16px/1.6 system-ui}"
        ".wrap{max-width:960px;margin:48px auto;padding:0 20px}"
        ".card{background:#111833;border:1px solid #1b254a;border-radius:16px;padding:24px}</style>"
        "<div class='wrap'><div class='card'>"
        "<h1>Analyse planning</h1>"
        "<p>Utilise la page d'accueil ou appelle l'API <code>POST /plannings/analyze</code>.</p>"
        "<p><a href='/'>← Accueil</a></p>"
        "</div></div>"
    )
    return HTMLResponse(html, status_code=200)

# ---------------------- API FICHIERS: LISTE & TÉLÉCHARGEMENTS ----------------------
def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} o"
    if n < 1024**2:
        return f"{n/1024:.1f} Ko"
    if n < 1024**3:
        return f"{n/1024**2:.1f} Mo"
    return f"{n/1024**3:.2f} Go"

@app.get("/downloads/list")
async def list_downloads():
    if not EXPORTS_DIR.exists():
        return {"files": []}
    items = []
    for p in sorted(EXPORTS_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
            stat = p.stat()
            items.append({
                "name": p.name,
                "size": stat.st_size,
                "size_fmt": _human_size(stat.st_size),
                "mtime": int(stat.st_mtime),
                "mtime_h": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "url": f"/downloads/file/{p.name}",
            })
    return {"files": items}

@app.get("/downloads/file/{name}")
async def download_file(name: str):
    # anti-path traversal
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Nom invalide.")
    path = EXPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=403, detail="Extension non autorisée.")
    return FileResponse(path, filename=path.name)

@app.get("/downloads/all.zip")
async def download_all_zip():
    files = [p for p in EXPORTS_DIR.iterdir()
             if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES]
    if not files:
        raise HTTPException(status_code=404, detail="Aucun fichier à zipper.")
    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=p.name)
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=exports_tout.zip"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)

from pydantic import BaseModel

class ZipSelection(BaseModel):
    names: List[str]

@app.post("/downloads/zip")
async def download_selection_zip(payload: ZipSelection):
    files = []
    seen = set()
    for name in payload.names:
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=400, detail=f"Nom invalide: {name}")
        p = EXPORTS_DIR / name
        if not p.is_file():
            raise HTTPException(status_code=404, detail=f"Introuvable: {name}")
        if p.suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=403, detail=f"Extension non autorisée: {name}")
        if name not in seen:
            files.append(p); seen.add(name)
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier sélectionné.")
    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=p.name)
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=selection.zip"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)
