from __future__ import annotations
import os, io, re, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound
from pydantic import BaseModel

# =========================================================
# Version / App
# =========================================================
VERSION = "UI-Conformite-1.1"
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
# Nomenclature CNAPS (MAJ avec tes nouveaux items)
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

    # Nouveaux éléments demandés
    {"key": "bulletins_paie", "label": "Bulletins de paye", "ext": ["pdf", "zip"]},
    {"key": "registre_unique_personnel", "label": "Registre unique du personnel", "ext": ["pdf", "xlsx", "xls"]},
    {"key": "modele_carte_pro", "label": "Modèle carte professionnelle (entreprise)", "ext": ["pdf", "png", "jpg", "jpeg"]},
    {"key": "factures_6m", "label": "Factures sur les 6 derniers mois", "ext": ["pdf", "zip"]},
    {"key": "captures_site_web", "label": "Captures de toutes les pages du site internet", "ext": ["png", "jpg", "jpeg", "zip", "pdf"]},
]
ALLOWED_SUFFIXES = {f".{e.lower()}" for d in DOCS for e in d["ext"]}
MAX_BYTES = 25 * 1024 * 1024  # 25 Mo

# =========================================================
# Seed UI (templates + css) — adapte NAV & contenus
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
          <a href="/analyse-conformite" class="{% if request.url.path.startswith('/analyse-conformite') %}active{% endif %}">Analyse de conformité</a>
          <a href="/cnaps" class="{% if request.url.path.startswith('/cnaps') %}active{% endif %}">CNAPS</a>
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
  <p class="muted">
    Cette application permet d'auditer une société de sécurité privée afin de vérifier sa conformité aux articles du livre 6 du Code de la Sécurité Intérieure.
  </p>
  <div class="card">
    <p>Utilisez le menu en haut pour lancer une <b>Analyse de conformité</b> ou gérer les pièces <b>CNAPS</b>.</p>
  </div>
{% endblock %}""",

    # Nouvelle page "Analyse de conformité"
    "conformite.html": """{% extends "base.html" %}
{% block title %}CSI — Analyse de conformité{% endblock %}
{% block content %}
  <h1>Analyse de conformité</h1>

  <div class="cards">
    <div class="card">
      <h3>Analyse des plannings</h3>
      <p class="muted small">Colle l’URL de ton planning puis clique <b>Analyser</b>.</p>
      <input id="planning-url" type="url" placeholder="https://exemple.tld/planning" />
      <div class="row">
        <button id="btn-analyze-planning">Analyser</button>
        <span id="planning-status" class="muted"></span>
      </div>
      <div id="planning-error" class="error" style="display:none"></div>
      <div id="planning-result" style="display:none" class="small"></div>
    </div>

    <div class="card">
      <h3>Analyse des pièces CNAPS</h3>
      <p class="muted small">Clique sur <b>Analyser</b> pour auditer les fichiers déjà téléversés dans chaque catégorie.</p>
      <div id="cnaps-analyses"></div>
    </div>
  </div>

  <script>
    // ======== Analyse Planning (utilise l’endpoint existant si présent) ========
    const pUrl = document.getElementById('planning-url');
    const pBtn = document.getElementById('btn-analyze-planning');
    const pSt  = document.getElementById('planning-status');
    const pErr = document.getElementById('planning-error');
    const pRes = document.getElementById('planning-result');

    pBtn.addEventListener('click', async ()=>{
      const u = (pUrl.value||'').trim();
      pErr.style.display='none'; pRes.style.display='none'; pSt.textContent='Analyse en cours…';
      if(!u){ pErr.textContent='Merci de saisir une URL.'; pErr.style.display='block'; pSt.textContent=''; return; }
      try{
        // on tente /plannings/analyze (ton routeur existant)
        const r = await fetch('/plannings/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url:u}) });
        const j = await r.json().catch(()=>({}));
        if(!r.ok || !j.ok){ throw new Error(j?.message || 'Analyse planning indisponible.'); }
        pSt.textContent=''; pRes.style.display='block';
        pRes.innerHTML = '<pre>'+JSON.stringify(j.data, null, 2)+'</pre>';
      }catch(e){
        pSt.textContent=''; pErr.textContent = e.message||e; pErr.style.display='block';
      }
    });

    // ======== Analyse CNAPS (boutons Analyser par catégorie) ========
    const CNAPS_DOCS = {{ DOCS | tojson }};
    const container = document.getElementById('cnaps-analyses');

    function row(d){
      const id = 'a-' + d.key;
      return `
        <div class="row" style="align-items:center">
          <div style="min-width:320px"><b>${d.label}</b> <span class="muted small">(${d.ext.join('/').toUpperCase()})</span></div>
          <button onclick="runAna('${d.key}', '${d.label.replace(/'/g,"\\'")}')">Analyser</button>
          <span id="${id}-st" class="muted small"></span>
        </div>
        <div id="${id}-out" class="small" style="margin:6px 0 12px 0"></div>
      `;
    }

    window.runAna = async (key, label)=>{
      const st = document.getElementById('a-'+key+'-st');
      const out = document.getElementById('a-'+key+'-out');
      st.textContent = 'Analyse en cours…'; out.innerHTML = '';
      try{
        const r = await fetch('/analyze/cnaps/'+encodeURIComponent(key));
        const j = await r.json();
        if(!r.ok || !j.ok){ throw new Error(j?.detail || 'Analyse indisponible'); }
        st.textContent = '';
        const files = j.files||[];
        if(files.length===0){
          out.innerHTML = `<div class="muted">Aucun fichier trouvé pour <b>${label}</b>.</div>`;
        }else{
          const rows = files.map(f=>`<tr><td>${f.name}</td><td>${f.size_fmt}</td><td>${f.mtime_h}</td><td>${f.flags?.join(', ')||''}</td></tr>`).join('');
          out.innerHTML = `
            <div class="muted">Résultat: ${files.length} fichier(s).</div>
            <div class="tablewrap">
              <table>
                <thead><tr><th>Fichier</th><th>Taille</th><th>Modifié</th><th>Remarques</th></tr></thead>
                <tbody>${rows}</tbody>
              </table>
            </div>`;
        }
      }catch(e){
        st.textContent = '';
        out.innerHTML = `<div class="error">${e.message||e}</div>`;
      }
    };

    container.innerHTML = CNAPS_DOCS.map(row).join('');
  </script>
{% endblock %}""",

    # Page CNAPS (upload / gestion)
    "cnaps.html": """{% extends "base.html" %}
{% block title %}CSI — CNAPS{% endblock %}
{% block content %}
  <h1>CNAPS — Téléversement et gestion des pièces</h1>
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
    for name, content in SEED_TEMPLATES.items():
        dest = TEMPLATES_DIR / name
        if not dest.exists():
            dest.write_text(content, encoding="utf-8")
    for name, content in SEED_STATIC.items():
        dest = STATIC_DIR / name
        if not dest.exists():
            dest.write_text(content, encoding="utf-8")

try:
    seed_ui_files()
except Exception:
    pass

# Static + templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
TEMPLATES = Jinja2Templates(directory=str(TEMPLATES_DIR))

# =========================================================
# Option : routeur planning existant (si présent)
# =========================================================
try:
    from app.plannings.router import router as planning_router
    app.include_router(planning_router)  # expose /plannings/analyze
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
    try:
        return TEMPLATES.TemplateResponse(name, {**context, "request": request})
    except TemplateNotFound:
        html = f"""<!doctype html><meta charset="utf-8">
<title>CSI</title>
<link rel="stylesheet" href="/static/style.css">
<div class="container">
  <h1>CSI — Interface</h1>
  <p class="muted">Template <b>{name}</b> introuvable. L'UI a été auto-seedée — actualise la page.</p>
  <ul>
    <li><a href="/">Accueil</a></li>
    <li><a href="/analyse-conformite">Analyse de conformité</a></li>
    <li><a href="/cnaps">CNAPS</a></li>
    <li><a href="/docs" target="_blank">Docs</a></li>
  </ul>
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
# PAGES
# =========================================================
@app.get("/", include_in_schema=False)
async def home(request: Request):
    return render_template(request, "index.html", {"version": VERSION})

@app.get("/analyse-conformite", include_in_schema=False)
async def conformite(request: Request):
    return render_template(request, "conformite.html", {"version": VERSION, "DOCS": DOCS})

@app.get("/cnaps", include_in_schema=False)
async def cnaps_page(request: Request):
    return render_template(request, "cnaps.html", {"version": VERSION, "DOCS": DOCS})

# (NB: plus de route /analyse-planning en haut — c’est intégré à /analyse-conformite)

# =========================================================
# API CNAPS (upload & fichiers)
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
# API Analyses (boutons "Analyser")
# =========================================================
class CNAPSSummary(BaseModel):
    ok: bool
    kind: str
    label: str
    files: List[Dict]

def _doc_by_key(key: str) -> Optional[Dict]:
    for d in DOCS:
        if d["key"] == key:
            return d
    return None

@app.get("/analyze/cnaps/{kind}")
async def analyze_cnaps(kind: str):
    d = _doc_by_key(kind)
    if not d:
        raise HTTPException(404, "Catégorie inconnue.")
    dirp = _kind_dir(kind)
    files = []
    for p in sorted(dirp.iterdir()):
        if p.is_file():
            st = p.stat()
            flags = []
            # petites heuristiques : extension attendue, taille nulle, date très ancienne
            if p.suffix.lower() not in {'.'+e for e in d["ext"]}:
                flags.append("extension inattendue")
            if st.st_size == 0:
                flags.append("fichier vide")
            if datetime.fromtimestamp(st.st_mtime).year < 2020:
                flags.append("très ancien")
            files.append({
                "name": p.name,
                "size": st.st_size,
                "size_fmt": _human_size(st.st_size),
                "mtime": int(st.st_mtime),
                "mtime_h": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "flags": flags
            })
    return {"ok": True, "kind": kind, "label": d["label"], "files": files}

@app.get("/analyze/cnaps")
async def analyze_cnaps_all():
    out = {}
    for d in DOCS:
        r = await analyze_cnaps(d["key"])  # type: ignore
        out[d["key"]] = r["files"]
    return {"ok": True, "data": out}
