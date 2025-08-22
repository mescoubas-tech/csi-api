# app/main.py
from __future__ import annotations
import os, io, re
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse

# ----- Version visible dans /health
VERSION = "CNAPS-UI-3.0"

app = FastAPI(title="CSI API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ----- Répertoires (uploads persistants dans le repo déployé)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CNAPS_DIR = Path(os.getenv("CNAPS_DIR", PROJECT_ROOT / "uploads" / "cnaps")).resolve()
CNAPS_DIR.mkdir(parents=True, exist_ok=True)

# ----- Spécification des pièces (comme ta page)
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
    # Ajoute d’autres entrées si tu veux compléter toute la liste
]
ALLOWED_SUFFIXES = {f".{e.lower()}" for d in DOCS for e in d["ext"]}
MAX_BYTES = 25 * 1024 * 1024  # 25 Mo

# ----- Optionnel : inclure ton routeur “plannings” s’il existe
try:
    from app.plannings.router import router as planning_router
    app.include_router(planning_router)
except Exception:
    pass

# ==================== HEALTH & DEBUG ====================
@app.get("/health", include_in_schema=False)
async def health():
    return {"status":"ok", "version": VERSION, "cnaps_dir": str(CNAPS_DIR)}

@app.get("/__debug", include_in_schema=False)
async def debug():
    return {
        "version": VERSION,
        "cwd": os.getcwd(),
        "cnaps_dir": str(CNAPS_DIR),
        "kinds": [d["key"] for d in DOCS],
        "files": sorted([p.as_posix() for p in CNAPS_DIR.rglob("*") if p.is_file()]),
    }

# ==================== UI: ACCUEIL ====================
@app.get("/", include_in_schema=False)
async def home():
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>CSI • Accueil</title><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>body{margin:0;background:#0b1020;color:#e6e9f2;font:16px/1.6 system-ui}"
        ".wrap{max-width:980px;margin:48px auto;padding:0 20px}"
        ".card{background:#111833;border:1px solid #1b254a;border-radius:16px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.3)}"
        "a{color:#6aa1ff;text-decoration:none}.pill{display:inline-block;margin:8px 8px 0 0;"
        "padding:10px 14px;border-radius:10px;border:1px solid #2a3a75;background:#1a2a6a}"
        ".muted{color:#9aa3b2}</style>"
        "<div class='wrap'><div class='card'>"
        "<h1>CSI API</h1>"
        "<p><a class='pill' href='/cnaps'>🧾 Analyse de conformité CNAPS — Téléversement</a>"
        "<a class='pill' href='/docs' target='_blank'>📘 Docs API</a>"
        "<a class='pill' href='/health' target='_blank'>🩺 Health</a></p>"
        f"<p class='muted'>Version : {VERSION}</p>"
        "</div></div>"
    )
    return HTMLResponse(html)

# ==================== UI: CNAPS (téléversement) ====================
@app.get("/cnaps", include_in_schema=False)
async def cnaps_page():
    # La page reconstruit la grille des cartes + la nomenclature, comme sur ta capture
    html = """
<!doctype html><meta charset="utf-8">
<title>Analyse de conformité CNAPS — Téléversement</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#0b1020;--panel:#111833;--muted:#94a3b8;--accent:#60a5fa;--ok:#22c55e;--border:#1b254a;--text:#e6e9f2}
  *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#0b1020,#0e1630);color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial}
  a{color:var(--accent);text-decoration:none}
  .container{max-width:1200px;margin:40px auto;padding:0 20px}
  h1{margin:0 0 12px;font-size:30px}
  .nav{margin:4px 0 20px}
  .grid{display:grid;grid-template-columns:1fr 370px;gap:22px}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:18px}
  .row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
  .input{flex:1;min-width:220px;border:1px solid #26325f;background:#0d1330;color:#eaf1ff;border-radius:12px;padding:10px 12px;outline:none}
  .cards{display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:14px}
  .card{border:1px dashed #26406a;background:rgba(17,24,51,.5);border-radius:14px;padding:14px}
  .card.ok{border-style:solid;border-color:#1f6d3a;background:rgba(16,53,30,.35)}
  .card h3{margin:0 0 2px;font-size:16px}
  .tag{display:inline-block;font-size:12px;color:#cbd5e1;border:1px solid #2a3a75;border-radius:20px;padding:2px 8px;margin-right:6px}
  .files{margin-top:8px;color:#cbd5e1;font-size:13px;word-break:break-all}
  .files a{color:#cbd5e1}
  .actions{margin-top:8px;display:flex;gap:8px;align-items:center}
  button{cursor:pointer;border:1px solid #2a3a75;background:#1a2a6a;color:#eaf1ff;padding:8px 12px;border-radius:10px}
  .right ul{margin:10px 0 0 18px;padding:0}
  .muted{color:var(--muted)}
  .small{font-size:13px}
</style>
<div class="container">
  <h1>Analyse de conformité CNAPS — Téléversement</h1>
  <div class="nav"><a href="/">Accueil</a> · <a href="/docs" target="_blank">Docs</a></div>

  <div class="grid">
    <div class="panel">
      <div class="row">
        <input class="input" placeholder="Nom de l’entreprise">
        <input class="input" placeholder="Site internet (optionnel)">
      </div>

      <div id="cards" class="cards"></div>
      <p class="muted small">Taille max : 25 Mo par fichier.</p>
    </div>

    <div class="right panel">
      <h2 style="margin:0 0 8px">Nomenclature des pièces</h2>
      <ul id="nomenclature" class="small"></ul>
    </div>
  </div>
</div>

<script>
const DOCS = %DOCS_JSON%;
const acceptFor = k => DOCS.find(d=>d.key===k).ext.map(e=>'.'+e).join(',');

function cardTemplate(d){
  return `
  <div class="card" id="card-${d.key}">
    <h3>${d.label} <span class="muted small">(${d.ext.join('/').toUpperCase()})</span> <span class="state"></span></h3>
    <div class="files"></div>
    <div class="actions">
      <input type="file" id="file-${d.key}" style="display:none" accept="${d.ext.map(e=>'.'+e).join(',')}">
      <button onclick="chooseFile('${d.key}')">Choisir un fichier</button>
      <button class="muted small" onclick="refresh()">Rafraîchir</button>
    </div>
  </div>`;
}

function chooseFile(kind){
  const input = document.getElementById('file-'+kind);
  input.onchange = async (ev)=>{
    if(!ev.target.files || ev.target.files.length===0) return;
    const f = ev.target.files[0];
    const fd = new FormData();
    fd.append('kind', kind);
    fd.append('file', f);
    try{
      const r = await fetch('/cnaps/upload', { method:'POST', body: fd });
      const j = await r.json();
      if(!r.ok || !j.ok) throw new Error(j.detail || j.message || 'Erreur');
      refresh();
    }catch(e){ alert(e.message || e); }
    finally { ev.target.value=''; }
  };
  input.click();
}

async function remove(kind, name){
  if(!confirm('Supprimer '+name+' ?')) return;
  const r = await fetch('/cnaps/file/'+encodeURIComponent(kind)+'/'+encodeURIComponent(name), { method:'DELETE' });
  if(r.ok) refresh(); else alert('Suppression impossible');
}

function renderList(data){
  const wrap = document.getElementById('cards'); wrap.innerHTML='';
  DOCS.forEach(d=>{
    wrap.insertAdjacentHTML('beforeend', cardTemplate(d));
    const card = document.getElementById('card-'+d.key);
    const files = (data[d.key] || []);
    const filesDiv = card.querySelector('.files');
    const state = card.querySelector('.state');
    card.classList.toggle('ok', files.length>0);
    state.textContent = files.length>0 ? '✓' : '';
    filesDiv.innerHTML = files.length===0 ? "<span class='muted small'>Aucun fichier</span>"
      : files.map(f => `<div>• <a href="/cnaps/file/${encodeURIComponent(d.key)}/${encodeURIComponent(f.name)}" target="_blank">${f.name}</a>
        <span class='muted small'>(${f.size_fmt}, ${f.mtime_h})</span>
        <button class='small' onclick="remove('${d.key}', '${f.name.replace(/'/g,"\\'")}')">Supprimer</button></div>`).join('');
  });

  // Nomenclature
  const nom = document.getElementById('nomenclature');
  nom.innerHTML = DOCS.map(d=>`<li>${d.label}</li>`).join('');
}

async function refresh(){
  const r = await fetch('/cnaps/list'); const j = await r.json();
  renderList(j.data || {});
}

refresh();
</script>
"""
    import json
    html = html.replace("%DOCS_JSON%", json.dumps(DOCS))
    return HTMLResponse(html)
# ==================== API CNAPS: liste / upload / get / delete ====================
def _safe_filename(name: str) -> str:
    name = name.strip().replace("\x00", "")
    name = re.sub(r"[^\w\.-]+", "_", name, flags=re.U)
    return name[:180] or "fichier"

def _kind_dir(kind: str) -> Path:
    return (CNAPS_DIR / kind).resolve()

def _ensure_kind(kind: str):
    if kind not in {d["key"] for d in DOCS}:
        raise HTTPException(status_code=400, detail="Type de pièce inconnu.")
    d = _kind_dir(kind); d.mkdir(parents=True, exist_ok=True); return d

@app.get("/cnaps/list")
async def cnaps_list():
    data: Dict[str, List[Dict]] = {}
    for d in DOCS:
        k = d["key"]; dirp = _ensure_kind(k)
        items = []
        for p in sorted(dirp.iterdir()):
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                st = p.stat()
                def human(n:int):
                    return f"{n} o" if n<1024 else (f"{n/1024:.1f} Ko" if n<1024**2 else (f"{n/1024**2:.1f} Mo" if n<1024**3 else f"{n/1024**3:.2f} Go"))
                items.append({
                    "name": p.name,
                    "size": st.st_size,
                    "size_fmt": human(st.st_size),
                    "mtime": int(st.st_mtime),
                    "mtime_h": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        data[k] = items
    return {"ok": True, "data": data}

@app.post("/cnaps/upload")
async def cnaps_upload(kind: str = Form(...), file: UploadFile = File(...)):
    _ensure_kind(kind)
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Extension non autorisée: {ext}. Autorisées: {sorted(ALLOWED_SUFFIXES)}")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 25 Mo).")
    name = _safe_filename(file.filename)
    path = _kind_dir(kind) / name
    with open(path, "wb") as f:
        f.write(content)
    return {"ok": True, "message": "Fichier téléversé.", "name": name}

@app.get("/cnaps/file/{kind}/{name}")
async def cnaps_get(kind: str, name: str):
    _ensure_kind(kind)
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Nom invalide.")
    path = _kind_dir(kind) / name
    if not path.is_file(): raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(path, filename=path.name)

@app.delete("/cnaps/file/{kind}/{name}")
async def cnaps_del(kind: str, name: str):
    _ensure_kind(kind)
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Nom invalide.")
    path = _kind_dir(kind) / name
    if not path.is_file(): raise HTTPException(status_code=404, detail="Fichier introuvable.")
    path.unlink()
    return {"ok": True}

# ==================== ZIP de la sélection (optionnel) ====================
from pydantic import BaseModel
class ZipSel(BaseModel):
    kind: str
    names: List[str]

@app.post("/cnaps/zip")
async def cnaps_zip(sel: ZipSel):
    _ensure_kind(sel.kind)
    files = []
    for n in sel.names:
        if "/" in n or "\\" in n or ".." in n: raise HTTPException(400, "Nom invalide.")
        p = _kind_dir(sel.kind) / n
        if not p.is_file(): raise HTTPException(404, f"Introuvable: {n}")
        files.append(p)
    if not files: raise HTTPException(400, "Aucun fichier.")
    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition":"attachment; filename=selection.zip"})
