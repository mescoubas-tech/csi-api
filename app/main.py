from fastapi import FastAPI, Response
from .routers import analyze, rules, health, categories, export

app = FastAPI(
    title="CSI API",
    description="API d'analyse CSI",
    version="1.0.0"
)

# Route GET racine (status check)
@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok"}

# Route HEAD racine (pour éviter le 405 sur HEAD /)
@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)

# Inclusion des routers
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
