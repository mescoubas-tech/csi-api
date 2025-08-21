from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Initialisation de l'app FastAPI
app = FastAPI(title="CSI API", version="1.0.0")

# Montage des fichiers statiques (CSS, JS, images)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates (HTML)
templates = Jinja2Templates(directory="app/templates")

# Page d'accueil (ton interface Apple-like)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Route de vérification du service
@app.get("/status")
async def status():
    return {"status": "ok", "service": "csi-api", "docs": "/docs"}
