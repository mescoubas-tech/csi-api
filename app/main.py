# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.3")

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

# Health
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# ✅ Page d’accueil (ancienne interface)
@app.get("/", include_in_schema=False)
async def home(request: Request):
    ret
