from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from .routers import analyze, rules, health, categories, export

app = FastAPI(title="CSI API", version="1.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/",include_in_schema=False)
def root():
    return {"status": "ok"}
==> Running 'uvicorn app.main:app --host 0.0.0.0 --port $PORT'
INFO:     Started server process [66]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
INFO:     127.0.0.1:52896 - "HEAD / HTTP/1.1" 405 Method Not Allowed
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
==> 
==> Available at your primary URL https://csi-api-zqo8.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
INFO:     35.197.80.206:0 - "GET / HTTP/1.1" 200 OK
INFO:     109.210.232.106:0 - "GET / HTTP/1.1" 200 OK

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(rules.router)
app.include_router(categories.router)
app.include_router(export.router)
git add app/main.py
git commit -m "feat: handle HEAD / to silence Render health-check 405"
git push
