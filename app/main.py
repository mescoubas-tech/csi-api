# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Routers
from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.2")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static (si tu as des assets front) — adapte le chemin si nécessaire
# Exemple : dossier "app/static" avec ton JS/CSS
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass  # ignore si le dossier n'existe pas

# Routers
app.include_router(planning_router)

# Healthcheck pour Render
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# ✅ Corrige le 404 de "/": on redirige vers la doc
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs", status_code=302)

# (facultatif) Page simple en HTML si tu préfères un message
@app.get("/_landing", include_in_schema=False)
async def landing():
    return HTMLResponse(
        """
        <!doctype html><meta charset="utf-8">
        <title>CSI API</title>
        <style>body{font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial;padding:32px}</style>
        <h1>CSI API</h1>
        <p>Service en ligne ✅</p>
        <p><a href="/docs">Accéder à la documentation OpenAPI</a></p>
        """,
        status_code=200
    )
