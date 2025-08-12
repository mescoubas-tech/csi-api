# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ⚠️ Assure-toi que ces modules existent à ces emplacements :
# app/routers/analyze.py, rules.py, health.py, categories.py, export.py
from .routers import analyze, rules, health, categories, export

app = FastAPI(title="CSI API", version="1.5.0")

# CORS = autoriser ton front Streamlit à appeler l’API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tu peux restreindre plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "CSI API v1.5.0"}

# ⬇️ Monte toutes les routes attendues par ton front
app.include_router(health.router)
app.include_router(analyze.router)       # /analyze/     (POST)
app.include_router(rules.router)         # /rules/       (GET/PUT/POST/DELETE)
app.include_router(categories.router)    # /categories   (GET/PUT/POST)
app.include_router(export.router)        # /export       (CSV endpoints)
