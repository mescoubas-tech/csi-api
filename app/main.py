# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# ⚠️ importe les routers APRÈS les imports FastAPI
from .plannings.router import router as planning_router

app = FastAPI(
    title="CSI API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS (ouvre large par défaut ; restreins si tu as des domaines précis)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ← remplace par ["https://ton-front.example"] si nécessaire
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes de base (pour éviter 404 sur /)
@app.get("/")
def home():
    # renvoie un message simple + lien vers /docs
    return JSONResponse({"status": "ok", "service": "csi-api", "docs": "/docs"})

@app.get("/health")
def root_health():
    return {"status": "ok", "service": "csi-api", "version": "0.1.0"}

# Erreurs homogènes
@app.exception_handler(Exception)
async def unhandled_error_handler(_req: Request, exc: Exception):
    # évite de crasher en 500 sans JSON
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# 👉 inclure les routers APRÈS la création de `app`
app.include_router(planning_router)
