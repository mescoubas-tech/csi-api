from pathlib import Path
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .routers import analyze, rules, health, categories, export

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="CSI API",
    description="API d'analyse CSI",
    version="1.0.0"
)

# Static assets (CSS, images, etc.)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Accueil minimaliste
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# HEAD / pour éviter le 405 des health-checks
@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)

# Routers API
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
mkdir -p app/templates app/static
# (crée les deux fichiers index.html et styles.css comme ci-dessus)

git add app/main.py app/templates/index.html app/static/styles.css
git commit -m "feat(ui): page d'accueil minimaliste + assets statiques"
git push
