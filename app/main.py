# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import plannings as plannings_router

app = FastAPI(title="CSI API", version="1.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restreins si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plannings_router.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
