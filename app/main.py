from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router


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

