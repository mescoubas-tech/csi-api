# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ importe via le paquet 'app'
from app.plannings.router import router as planning_router

app = FastAPI(title="CSI API", version="1.6.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreins si nécessaire
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planning_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
