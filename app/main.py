from __future__ import annotations
import os, io, re, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound

# =========================================================
# Version / App
# =========================================================
VERSION = "UI-Blanche-Autoseed-1.0"
app = FastAPI(title="CSI API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# =========================================================
# Dossiers
# =========================================================
BASE_DIR = Path(__file__).resolve().parent        # app/
PROJECT_ROOT = BASE_DIR.parent                    # repo root
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

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
CNAPS_DIR = (PROJECT_ROOT / "uploads" / "cnaps").resolve()
CNAPS_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# Données UI (CNAPS)
# =========================================================
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

# =========================================================
# Seed de l'UI (templates + css) si manquants
# =========================================================
SEED_TEMPLATES: Dict[str,str] = {
    "base.html": """<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <title>{% block title %}CSI{% endblock %}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <header class="topbar">
      <div class="container">
        <div class="brand">CSI</div>
        <nav class="tabs">
          <a href="/" class="{% if request.url.path=='/' %}active{% endif %}">Accueil</a>
          <a href="/analyse-planning" class="{% if request.url.path.startswith('/analyse-planning') %}active{% endif %}">Analyse planning</a>
          <a href="/cnaps" class="{% if request.url.path.startswith('/cnaps') %}active{% endif %}">CNAPS</a>
          <a href="/telechargements" class="{% if request.url.path.startswith('/telechargements') %}active{% endif %}">Téléchargements</a>
          <a href="/docs" target="_blank">Docs</a>
        </nav>
      </div>
    </header>
    <main class="container">{% block content %}{% endblock %}</main>
    <footer class="footer"><div class="container muted">Version : {{ version }}</div></footer>
  </body>
</html>""",
    "index.html": """{% extends "base.html" %}
{% block title %}CSI — Accueil{% endblock %}
{% block content %}
  <h1>Bienvenue</h1>
  <p class="muted">Choisissez un onglet ci-dessus pour démarrer.</p>
{% endblock %}""",
    "analyse_planning.html": """{% extends "base.html" %}
{% block title %}CSI — Analyse planning{% endblock %}
{% block content %}
  <h1>Analyse des plannings</h1>
  <div class="card">
    <label for="planning-url">URL du planning</label>
    <input id="planning-url" type="url" placeholder="https://exemple.tld/planning" />
    <div class="row">
      <button id="btn-analyze">Analyser</button>
      <span id="status" class="muted"></span>
    </div>
  </div>
  <div id="error" class="error" style="display:none"></div>
  <div id="result" style="display:none" class="card">
    <h3>Résultat</h3>
    <div id="meta" class="muted"></div>
    <h4>Constats</h4>
    <ul id="findings"></ul>
    <h4>Aperçu (10 premières lignes)</h4>
    <div id="preview"></div>
  </div>
  <script>
    const urlInput = document.getElementById('planning-url');
    const btn = document.getElementById('btn-analyze');
    const st = document.getElementById('status');
    const err = document.getElementById('error');
    const res = document.getElementById('result');
    btn.addEventListener('click', async ()=>{
      const u = urlInput.value.trim();
      err.style.display='none'; res.style.display='none'; st.textContent='Analyse en cours…';
      if(!u){ err.textContent='Merci de saisir une URL.'; err.style.display='block'; st.textContent=''; return; }
      try{
        const r = await fetch('/plannings/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url:u})});
        const j = await r.json();
        if(!r.ok || !j.ok){ throw new Error(j?.message || 'Analyse impossible.'); }
        st.textContent=''; res.style.display='block';
        document.getElementById('meta').textContent = 'Lignes : ' + (j.data?.meta?.rows ?? '?');
        const findings = document.getElementById('findings');
        findings.innerHTML = (j.data?.findings||[]).map(f=>`<li>${f.type?`[${f.type}] `:''}${f.message||JSON.stringify(f)}</li>`).join('') || '<li>Aucun constat.</li>';
        const rows = j.data?.preview || [];
        const preview = document.getElementById('preview');
        if(rows.length===0){ preview.innerHTML = "<p class='muted'>Aucun aperçu disponible.</p>"; }
        else{
          const cols = Object.keys(rows[0]);
          preview.innerHTML = "<table><thead><tr>"+cols.map(c=>`<th>${c}</th>`).join("")+"</tr></thead><tbody>"+
            rows.map(r=>"<tr>"+cols.map(c=>`<td>${r[c]??''}</td>`).join("")+"</tr>").join("")+
            "</tbody></table>";
        }
      }catch(e){
        st.textContent=''; err.textContent = e.message || e; err.style.display='block';
      }
    });
  </script>
{% endblock %}""",
    "cnaps.html": """{% extends "base.html" %}
{% block title %}CSI — CNAPS{% endblock %}
{% block content %}
  <h1>Analyse de conformité CNAPS — Téléversement</h1>
  <div class="grid">
    <div class="col">
      <div id="cards" class="cards"></div>
      <p class="muted small">Taille max : 25 Mo par fichier.</p>
    </div>
    <aside class="col">
      <div class="card"><h3>Nomenclature des pièces</h3><ul id="nomenclature" class="small"></ul></div>
    </aside>
  </div>
  <script>
    const DOCS = {{ DOCS | tojson }};
    function cardHtml(d, files){
      return `
      <div class="card ${files.length>0?'ok':''}" id="card-${d.key}">
        <h3>${d.label} <span class="muted small">(${d.ext.join('/').toUpperCase()})</span> <span class="state">${files.length>0?'✓':''}</span></h3>
        <div class="files">${
          files.length===0 ? "<span class='muted small'>Aucun fichier</span>"
            : files.map(f => \`• <a href="/cnaps/file/\${d.key}/\${f.name}" target="_blank">\${f.name}</a>
              <span class='muted small'>(\${f.size_fmt}, \${f.mtime_h})</span>
              <button class='small' onclick="removeFile('\${d.key}','\${f.name.replace(/'/g,"\\\\'")}')">Supprimer</button>\`
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
        const fd = new FormData(); fd.append('kind', kind); fd.append('file', f);
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
{% endblock %}""",
    "telechargements.html": """{% extends "base.html" %}
{% block title %}CSI — Téléchargements{% endblock %}
{% block content %}
  <h1>Tous les dossiers à télécharger</h1>
  <div class="row">
    <button id="btn-refresh">Rafraîchir</button>
    <a class="btn" href="/downloads/all.zip">Télécharger tout (ZIP)</a>
    <button id="btn-zip-selected">Télécharger la sélection (ZIP)</button>
  </div>
  <div id="status" class="muted">Chargement…</div>
  <div class="tablewrap">
    <table id="tbl">
      <thead><tr>
        <th><input type="checkbox" id="select-all"></th>
        <th>Nom</th><th>Taille</th><th>Modifié</th><th>Télécharger</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <script>
    const tbody = document.querySelector('#tbl tbody');
    const statusEl = document.getElementById('status');
    async function load(){
      statusEl.textContent='Chargement…'; tbody.innerHTML='';
      try{
        const r = await fetch('/downloads/list'); const j = await r.json();
        const rows = j.files||[];
        if(rows.length===0){ statusEl.textContent='Aucun fichier.'; return; }
        statusEl.textContent = rows.length+' fichier(s)';
        rows.forEach(f=>{
          const tr = document.createElement('tr');
          tr.innerHTML =
            `<td><input type="checkbox" class="sel" data-name="${f.name}"></td>`+
            `<td>${f.name}</td>`+
            `<td>${f.size_fmt}</td>`+
            `<td>${f.mtime_h}</td>`+
            `<td><a href="/downloads/file/${encodeURIComponent(f.name)}">Télécharger</a></td>`;
          tbody.appendChild(tr);
        });
      }catch(e){ statusEl.textContent='Erreur: '+(e.message||e); }
    }
    document.getElementById('btn-refresh').addEventListener('click', load);
    document.getElementById('select-all').addEventListener('change', e=>{
      document.querySelectorAll('input.sel').forEach(cb=>cb.checked=e.target.checked);
    });
    document.getElementById('btn-zip-selected').addEventListener('click', async ()=>{
      const names=[...document.querySelectorAll('input.sel:checked')].map(cb=>cb.dataset.name);
      if(names.length===0){ alert('Sélectionne au moins un fichier.'); return; }
      try{
        const r = await fetch('/downloads/zip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({names})});
        if(!r.ok){ const j=await r.json().catch(()=>({detail:'Erreur'})); throw new Error(j.detail||'Erreur zip'); }
        const blob = await r.blob(); const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href=url; a.download='selection.zip'; a.click(); URL.revokeObjectURL(url);
      }catch(e){ alert(e.message||e); }
    });
    load();
  </script>
{% endblock %}""",
}

SEED_STATIC: Dict[str,str] = {
    "style.css": """:root{
  --bg:#fff; --text:#0f172a; --muted:#6b7280;
  --primary:#1f2937; --accent:#0ea5e9; --border:#e5e7eb; --card:#ffffff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial}
.container{max-width:1100px;margin:32px auto;padding:0 20px}
a{color:#0ea5e9;text-decoration:none}
h1{margin:0 0 16px}
h3{margin:0 0 8px}
.muted{color:var(--muted)} .small{font-size:13px}
.row{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 18px}
.btn, button{cursor:pointer;border:1px solid #d1d5db;background:#f3f4f6;color:#111827;padding:8px 12px;border-radius:8px}
input[type=url], input[type=text]{width:100%;max-width:600px;padding:10px 12px;border-radius:8px;border:1px solid var(--border)}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin:12px 0}
.topbar{background:#f8fafc;border-bottom:1px solid var(--border)}
.topbar .container{display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:700}
.tabs a{display:inline-block;padding:10px 12px;border-radius:8px;margin-left:6px;color:#1f2937}
.tabs a.active{background:#e5e7eb}
.tablewrap{overflow:auto}
table{width:100%;border-collapse:collapse;background:var(--card)}
th,td{border:1px solid var(--border);padding:8px;text-align:left}
.grid{display:grid;grid-template-columns:1fr 320px;gap:16px}
.cards{display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:12px}
.files{margin-top:6px}
.card.ok{border-color:#16a34a}
.error{color:#dc2626}
"""
}

def seed_ui_files() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    # templates
    for name, content in SEED_TEMPLATES.items():
        dest = TEMPLATES_DIR / name
        if not dest.exists():
            dest.write_text(content, encoding="utf-8")
    # css
    for name, content in SEED_STATIC.items():
        dest = STATIC_DIR / name
        if not dest.exists():
            dest.write_text(content, encoding="utf-8")

# Seed à l'import (au démarrage du process)
try:
    seed_ui_files()
except Exception as e:
    # On ne bloque pas l'app si le FS est en lecture seule; on aura un fallback HTML plus bas.
    pass

# Templating & Static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
TEMPLATES = Jinja2Templates(directory=str(TEMPLATES_DIR))

# =========================================================
# Option : routeur planning existant
# =========================================================
try:
    from app.plannings.router import router as planning_router
    app.include_router(planning_router)
except Exception:
    pass

# =========================================================
# Utils
# =========================================================
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

def render_template(request: Request, name: str, context: dict) -> HTMLResponse:
    """Rend un template; si absent, renvoie un fallback HTML blanc pour éviter les 500."""
    try:
        return TEMPLATES.TemplateResponse(name, {**context, "request": request})
    except TemplateNotFound:
        # Fallback minimal (fond blanc)
        html = f"""<!doctype html><meta charset="utf-8">
<title>CSI</title>
<link rel="stylesheet" href="/static/style.css">
<div class="container">
  <h1>CSI — Interface</h1>
  <p class="muted">Template <b>{name}</b> introuvable. L'UI a été auto-seedée, re-déploie ou rafraîchis la page.</p>
  <ul>
    <li><a href="/">Accueil</a></li>
    <li><a href="/analyse-planning">Analyse planning</a></li>
    <li><a href="/cnaps">CNAPS</a></li>
    <li><a href="/telechargements">Téléchargements</a></li>
    <li><a href="/docs" target="_blank">Docs</a></li>
  </ul>
  <pre class="muted small">templates: {TEMPLATES_DIR}</pre>
</div>"""
        return HTMLResponse(html, status_code=200)

# =========================================================
# Health / Debug
# =========================================================
@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "ok",
        "version": VERSION,
        "templates_dir": str(TEMPLATES_DIR),
        "static_dir": str(STATIC_DIR),
        "exports_dir": str(EXPORTS_DIR),
        "cnaps_dir": str(CNAPS_DIR),
        "templates_present": sorted(p.name for p in TEMPLATES_DIR.glob("*.html")),
        "static_present": sorted(p.name for p in STATIC_DIR.glob("*")),
    }

@app.get("/__debug", include_in_schema=False)
async def debug():
    return {
        "cwd": os.getcwd(),
        "ls_templates": sorted(p.name for p in TEMPLATES_DIR.glob("*.html")),
        "ls_static": sorted(p.name for p in STATIC_DIR.glob("*")),
        "exports": sorted(p.name for p in EXPORTS_DIR.glob("*"))[:100],
        "uploads_cnaps": sorted(str(p.relative_to(CNAPS_DIR)) for p in CNAPS_DIR.rglob("*"))[:100],
    }

# =========================================================
# PAGES (UI blanche avec onglets)
# =========================================================
@app.get("/", include_in_schema=False)
async def home(request: Request):
    return render_template(request, "index.html", {"version": VERSION})

@app.get("/analyse-planning", include_in_schema=False)
async def analyse_planning_page(request: Request):
    return render_template(request, "analyse_planning.html", {"version": VERSION})

@app.get("/cnaps", include_in_schema=False)
async def cnaps_page(request: Request):
    return render_template(request, "cnaps.html", {"version": VERSION, "DOCS": DOCS})

@app.get("/telechargements", include_in_schema=False)
async def telechargements_page(request: Request):
    return render_template(request, "telechargements.html", {"version": VERSION})

# =========================================================
# API CNAPS
# =========================================================
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

# =========================================================
# API Téléchargements (exports)
# =========================================================
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
