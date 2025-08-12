from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Téléverser — Analyse de conformité CNAPS</title>
  <link rel="stylesheet" href="/static/styles.css" />
  <style>
    .form { width:min(980px,92vw); margin:32px auto; background:var(--card); border:1px solid var(--border); border-radius:16px; padding:18px; }
    .row { display:grid; grid-template-columns: 1fr 2fr; gap:12px; align-items:center; margin-bottom:12px; }
    label { font-weight:600; }
    input[type="text"] { width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--border); background:transparent; color:var(--fg); }
    input[type="file"] { width:100%; }
    .hint { color:var(--muted); font-size:12px; }
    .actions { display:flex; gap:12px; justify-content:flex-end; margin-top:16px; }
    .btn { display:inline-block; padding:10px 16px; border-radius:999px; border:1px solid var(--border); text-decoration:none; font-weight:600; background:var(--fg); color:var(--bg); }
    .btn.secondary { background:transparent; color:var(--fg); }
  </style>
</head>
<body>
  <header class="wrap">
    <h1>Analyse de conformité CNAPS</h1>
    <nav><a href="/">Accueil</a> · <a href="/docs">Docs</a></nav>
  </header>

  <main class="wrap">
    <h2>Onglet Téléversement</h2>
    <p class="hint">Chargez vos pièces (PDF, DOCX, XLSX, ZIP). Chaque bloc accepte plusieurs fichiers.</p>

    <form class="form" action="/upload" method="post" enctype="multipart/form-data">
      <div class="row">
        <label>Nom de l’entreprise *</label>
        <input required type="text" name="company_name" placeholder="Ex : SECURITAS PROVENCE" />
      </div>
      <div class="row">
        <label>Site internet</label>
        <input type="text" name="website_url" placeholder="https://www.exemple.com" />
      </div>

      <hr style="border:0;border-top:1px solid var(--border);margin:16px 0;">

      <div class="row"><label>Grand livre de compte</label><input type="file" name="grand_livre" multiple></div>
      <div class="row"><label>Liasse fiscale</label><input type="file" name="liasse_fiscale" multiple></div>
      <div class="row"><label>Relevés bancaires (6 mois)</label><input type="file" name="releves_bancaires" multiple></div>
      <div class="row"><label>Factures</label><input type="file" name="factures" multiple></div>
      <div class="row"><label>Factures sous-traitants</label><input type="file" name="factures_sous_traitants" multiple></div>
      <div class="row"><label>Plannings des agents</label><input type="file" name="plannings_agents" multiple></div>
      <div class="row"><label>Autorisation d’exercer</label><input type="file" name="autorisation_exercer" multiple></div>
      <div class="row"><label>Agrément dirigeant</label><input type="file" name="agrement_dirigeant" multiple></div>
      <div class="row"><label>Registre du personnel</label><input type="file" name="registre_personnel" multiple></div>
      <div class="row"><label>Registre des contrôles internes</label><input type="file" name="registre_controles_internes" multiple></div>
      <div class="row"><label>Extrait KBIS</label><input type="file" name="extrait_kbis" multiple></div>
      <div class="row"><label>Statuts de l’entreprise</label><input type="file" name="statuts_entreprise" multiple></div>
      <div class="row"><label>Justificatifs DPAE</label><input type="file" name="justificatifs_dpae" multiple></div>

      <div class="actions">
        <a class="btn secondary" href="/">Annuler</a>
        <button class="btn" type="submit">Téléverser</button>
      </div>
      <p class="hint">Taille max : {{ 25 }} Mo / fichier (modifiable côté serveur).</p>
    </form>
  </main>
</body>
</html>


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="CSI API", description="API d'analyse CSI", version="1.0.0")

# Fichiers statiques (CSS, images…)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Page d'accueil minimaliste
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# HEAD / pour éviter le 405 de certains health-checks
@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)

# Routers API
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
from .routers import analyze, rules, health, categories, export, upload  # + upload

# ...
from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router

