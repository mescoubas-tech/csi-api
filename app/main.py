# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.3")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# API
app.include_router(planning_router)

# Healthcheck
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# Page d’accueil (UI)
@app.get("/", include_in_schema=False)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Page d’analyse (UI)
@app.get("/analyse-planning", include_in_schema=False)
async def analyse_planning_page(request: Request):
    return templates.TemplateResponse("analyse_planning.html", {"request": request})

# (facultatif) page de test rapide
@app.get("/_landing", include_in_schema=False)
async def landing():
    return HTMLResponse("<h1>CSI API</h1><p>Service en ligne ✅</p><p><a href='/'>UI</a> • <a href='/docs'>Docs</a></p>")
