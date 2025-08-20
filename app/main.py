# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 👉 importe le router APRÈS les imports FastAPI
from .plannings.router import router as planning_router


# --- création de l'application FastAPI (doit être avant tout app.include_router) ---
app = FastAPI(
    title="CSI API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# (optionnel) CORS permissif ; ajuste si besoin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ← remplace par ta liste de domaines si nécessaire
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- inclusion des routers ---
# ton router "planning-audit"
app.include_router(planning_router)

# si tu as d'autres routers existants, ajoute-les ici :
# from .autre_module.router import router as autre_router
# app.include_router(autre_router)


# --- endpoints de base (facultatif) ---
@app.get("/health")
def root_health():
    return {"status": "ok", "service": "csi-api", "version": "0.1.0"}
