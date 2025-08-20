# app/plannings/router.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import io, os, time, json

==> Exited with status 1
     ==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'uvicorn app.main:app --host 0.0.0.0 --port $PORT'
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/bin/uvicorn", line 8, in <module>
    sys.exit(main())
             ~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/click/core.py", line 1442, in __call__
    return self.main(*args, **kwargs)
           ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/click/core.py", line 1363, in main
    rv = self.invoke(ctx)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/click/core.py", line 1226, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/click/core.py", line 794, in invoke
    return callback(*args, **kwargs)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/main.py", line 410, in main
    run(
    ~~~^
        app,
        ^^^^
    ...<45 lines>...
        h11_max_incomplete_event_size=h11_max_incomplete_event_size,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/main.py", line 577, in run
    server.run()
    ~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/server.py", line 65, in run
    return asyncio.run(self.serve(sockets=sockets))
           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/asyncio/runners.py", line 195, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "/usr/local/lib/python3.13/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/server.py", line 69, in serve
    await self._serve(sockets)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/server.py", line 76, in _serve
    config.load()
    ~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/config.py", line 434, in load
    self.loaded_app = import_from_string(self.app)
                      ~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/importer.py", line 22, in import_from_string
    raise exc from None
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/uvicorn/importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
  File "/usr/local/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/opt/render/project/src/app/main.py", line 11, in <module>
    from .plannings.router import router as planning_router
  File "/opt/render/project/src/app/plannings/router.py", line 6, in <module>
    from .config import SETTINGS, RuleSettings
ModuleNotFoundError: No module named 'app.plannings.config'
# >>> IMPORTANT : définir le router AVANT d’utiliser @router.xxx <<<
router = APIRouter(prefix="", tags=["planning-audit"])

@router.get("/planning/health")
def health():
    return {"status": "ok", "rules": SETTINGS.rules.dict()}

@router.get("/planning/rules")
def get_rules():
    return SETTINGS.rules.dict()

@router.put("/planning/rules")
def update_rules(payload: dict):
    try:
        new_rules = RuleSettings(**{**SETTINGS.rules.dict(), **payload})
        SETTINGS.rules = new_rules
        return {"ok": True, "rules": new_rules.dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/planning/analyze")
async def post_analyze(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = load_schedule(content, file.filename)
        result = analyze(df)
        return JSONResponse(content=json.loads(result.model_dump_json()))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/planning/export/report")
async def post_export_report(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = load_schedule(content, file.filename)
        result = analyze(df)

        # Option A : écriture disque puis retour (si FileSystem autorisé)
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out_path = os.path.join(reports_dir, f"rapport_audit_{int(time.time())}.pdf")
        export_pdf(result, out_path)
        with open(out_path, "rb") as f:
            pdf_bytes = f.read()
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                                 headers={"Content-Disposition": 'attachment; filename="rapport_audit.pdf"'})

        # Option B (alternative sans écriture disque) :
        # from reportlab.pdfgen import canvas
        # from reportlab.lib.pagesizes import A4
        # from reportlab.lib.units import cm
        # from reportlab.lib.utils import simpleSplit
        # from datetime import datetime
        # buf = io.BytesIO()
        # c = canvas.Canvas(buf, pagesize=A4)
        # ... (génère le PDF en mémoire) ...
        # buf.seek(0)
        # return StreamingResponse(buf, media_type="application/pdf",
        #                          headers={"Content-Disposition": 'attachment; filename="rapport_audit.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
