from __future__ import annotations
import os, io, re, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse

# ==================== Version ====================
VERSION = "CNAPS-UI-3.2"

# ==================== App ====================
app = FastAPI(title="CSI API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Dossiers ====================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

def ensure_exports_dir() -> Path:
    """
    Retourne un dossier exploitable pour les téléchargements.
    Si 'exports' existe mais n'est pas un dossier, on bascule sur 'exports_data'.
    """
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

# Dossier CNAPS (stockage des uploads)
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

# ==================== Optionnel : inclure ton routeur métier ====================
try:
    from app.plannings.router import router as planning_router  # s'il existe
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
        "cnaps_dir": str(CNAPS_DIR),
        "exports_dir": str(EXPORTS_DIR),
    }

@app.get("/__debug", include_in_schema=False)
async def debug():
    return {
        "version": VERSION,
        "cwd": os.getcwd(),
        "cnaps_dir": str(CNAPS_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "docs_keys": [d["key"] for d in DOCS],
    }

# ==================== Accueil ====================
@app.get("/", include_in_schema=False)
async def home():
    html = f"""
<!doctype html><meta charset="utf-8">
<title>CSI • Accueil</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;background:#0b1020;color:#e6e9f2;font:16px/1.6 system-ui}}
  .wrap{{max-width:980px;margin:48px auto;padding:0 20px}}
  .card{{background:#111833;border:1px solid #1b254a;border-radius:16px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.3)}}
  a{{color:#6aa1ff;text-decoration:none}}
  .pill{{display:inline-block;margin:8px 8px 0 0;padding:10px 14px;border-radius:10px;border:1px solid #2a3a75;background:#1a2a6a}}
  .muted{{color:#9aa3b2}}
</style>
<div class="wrap"><div class="card">
  <h1>CSI API</h1>
  <p>
    <a class="pill" href="/cnaps">🧾 Analyse de conformité CNAPS</a>
    <a class="pill" href="/docs" target="_blank">📘 Docs API</a>
    <a class="pill" href="/health" target="_blank">🩺 Health</a>
  </p>
  <p class="muted">Version : {VERSION}</p>
</div></div>
"""
    return HTMLResponse(html, status_code=200)

# ==================== UI CNAPS (corrigée : aucun f-string dans le JS) ====================
@app.get("/cnaps", include_in_schema=False)
async def cnaps_page():
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
  .grid{display:grid;grid-template-columns:1fr 370px;gap:22px}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:18px}
  .cards{display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:14px}
  .card{border:1px dashed #26406a;background:rgba(17,24,51,.5);border-radius:14px;padding:14px}
  .card.ok{border-style:solid;border-color:#1f6d3a;background:rgba(16,53,30,.35)}
  .card h3{margin:0 0 2px;font-size:16px}
  .files{margin-top:8px;color:#cbd5e1;font-size:13px;word-break:break-all}
  .files a{color:#cbd5e1}
  .actions{margin-top:8px;display:flex;gap:8px;align-items:center}
  button{cursor:pointer;border:1px solid #2a3a75;background:#1a2a6a;color:#eaf1ff;padding:8px 12px;border-radius:10px}
  .right ul{margin:10px 0 0 18px;padding:0}
  .muted{color:var(--muted)} .small{font-size:13px}
</style>
<div class="container">
  <h1>Analyse de conformité CNAPS — Téléversement</h1>
  <div><a href="/">Accueil</a> · <a href="/docs" target="_blank">Docs</a></div>

  <div class="grid">
    <div class="panel">
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

function cardHtml(d, files){
  return `
  <div class="card ${files.length>0?'ok':''}" id="card-${d.key}">
    <h3>${d.label} <span class="muted small">(${d.ext.join('/').toUpperCase()})</span> <span class="state">${files.length>0?'✓':''}</span></h3>
    <div class="files">${
      files.length===0 ? "<span class='muted small'>Aucun fichier</span>"
        : files.map(f => `• <a href="/cnaps/file/${d.key}/${f.name}" target="_blank">${f.name}</a>
          <span class='muted small'>(${f.size_fmt})</span>
          <button class='small' onclick="removeFile('${d.key}','${f.name.replace(/'/g,"\\'")}')">Supprimer</button>`
        ).join("<br>")
    }</div>
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
      if(!r.ok){ const j=await r.json().catch(()=>({detail:'Erreur'})); throw new Error(j.detail||'Erreur upload'); }
      refresh();
    }catch(e){ alert(e.message||e); }
    finally{ ev.target.value=''; }
  };
  input.click();
}

async function removeFile(kind, name){
  if(!confirm('Supprimer '+name+' ?')) return;
  const r = await fetch('/cnaps/file/'+encodeURIComponent(kind)+'/'+encodeURIComponent(name), { method:'DELETE' });
  if(r.ok) refresh(); else alert('Suppression impossible');
}

async function refresh(){
  const r = await fetch('/cnaps/list'); const j = await r.json();
  const wrap = document.getElementById('cards'); wrap.innerHTML='';
  DOCS.forEach(d=>{
    const files = (j.data && j.data[d.key]) || [];
    wrap.insertAdjacentHTML('beforeend', cardHtml(d, files));
  });
  document.getElementById('nomenclature').innerHTML = DOCS.map(d=>`<li>${d.label}</li>`).join('');
}
refresh();
</script>
"""
    html = html.replace("%DOCS_JSON%", json.dumps(DOCS))
    return HTMLResponse(html, status_code=200)

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
    # validations
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

# ==================== (Option) ZIP de sélection ====================
from pydantic import BaseModel
class ZipSel(BaseModel):
    kind: str
    names: List[str]

@app.post("/cnaps/zip")
async def cnaps_zip(sel: ZipSel):
    if sel.kind not in {d["key"] for d in DOCS}:
        raise HTTPException(400, "Type de pièce inconnu.")
    files = []
    for n in sel.names:
        if "/" in n or "\\" in n or ".." in n:
            raise HTTPException(400, "Nom invalide.")
        p = _kind_dir(sel.kind) / n
        if not p.is_file():
            raise HTTPException(404, f"Introuvable: {n}")
        files.append(p)
    if not files:
        raise HTTPException(400, "Aucun fichier.")

    buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=selection.zip"},
    )
