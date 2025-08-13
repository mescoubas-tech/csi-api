from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router
from .routers.schedules import router as schedules_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="Analyse de conformité CNAPS",
    description="API d'analyse du Livre 6 du CSI",
    version="1.0.0"
)

# Servir /static (CSS, images…)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Page d'accueil (template HTML)
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Répondre OK aux HEAD /
@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)

# Routers API
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
app.include_router(upload_router)  # <= upload
app.include_router(schedules_router)
from .routers import analyze, rules, health, categories, export, schedules
# ...
app.include_router(schedules.router)
from .routers import analyze, rules, health, categories, export
from .routers.upload import router as upload_router
from .routers.schedules import router as schedules_router
try:
    from .routers.schedules import router as schedules_router
    app.include_router(schedules_router)
except Exception:
    # on démarre sans les routes schedules si le module manque
    pass
