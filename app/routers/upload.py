import os, re, time
from pathlib import Path
from typing import List, Optional

 File "/opt/render/project/src/app/routers/upload.py", line 6, in <module>
    from .routers import analyze, rules, health, categories, export
ModuleNotFoundError: No module named 'app.routers.routers'
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
  File "/opt/render/project/src/app/main.py", line 8, in <module>
    from .routers.upload import router as upload_router  # <= upload
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/app/routers/upload.py", line 6, in <module>
    from .routers import analyze, rules, health, categories, export
ModuleNotFoundError: No module named 'app.routers.routers'

from ..core.config import get_settings

router = APIRouter(tags=["upload"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# --- utils ---
SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

def _safe_name(s: str) -> str:
    s = s.strip().replace(" ", "_")
    return SAFE_CHARS.sub("", s)[:80] or "entreprise"

def _safe_file_name(name: str) -> str:
    base = os.path.basename(name)
    return _safe_name(base)

def _ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p

def _check_size(buf: bytes):
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    if len(buf) > max_bytes:
        raise HTTPException(413, f"Fichier trop volumineux (> {get_settings().MAX_UPLOAD_MB} Mo)")

# --- GET: page de téléversement ---
@router.get("/televerser", response_class=HTMLResponse, include_in_schema=False)
def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

# --- POST: réception des fichiers ---
@router.post("/upload")
async def upload_all(
    company_name: str = Form(...),
    website_url: Optional[str] = Form(None),

    grand_livre: List[UploadFile] = File([]),
    liasse_fiscale: List[UploadFile] = File([]),
    releves_bancaires: List[UploadFile] = File([]),
    factures: List[UploadFile] = File([]),
    factures_sous_traitants: List[UploadFile] = File([]),
    plannings_agents: List[UploadFile] = File([]),
    autorisation_exercer: List[UploadFile] = File([]),
    agrement_dirigeant: List[UploadFile] = File([]),
    registre_personnel: List[UploadFile] = File([]),
    registre_controles_internes: List[UploadFile] = File([]),
    extrait_kbis: List[UploadFile] = File([]),
    statuts_entreprise: List[UploadFile] = File([]),
    justificatifs_dpae: List[UploadFile] = File([]),
):
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        base = Path(get_settings().UPLOADS_DIR) / f"{_safe_name(company_name)}_{ts}"
        _ensure_dir(base)

        saved = []
        async def save_group(name: str, files: List[UploadFile]):
            if not files: return
            group_dir = _ensure_dir(str(base / name))
            for f in files:
                content = await f.read()
                _check_size(content)
                target = Path(group_dir) / _safe_file_name(f.filename or f"file_{int(time.time())}")
                with open(target, "wb") as out:
                    out.write(content)
                saved.append(str(target.relative_to(Path(get_settings()).PROJECT_ROOT)))

        # Sauvegarde par catégorie
        await save_group("grand_livre", grand_livre)
        await save_group("liasse_fiscale", liasse_fiscale)
        await save_group("releves_bancaires", releves_bancaires)
        await save_group("factures", factures)
        await save_group("factures_sous_traitants", factures_sous_traitants)
        await save_group("plannings_agents", plannings_agents)
        await save_group("autorisation_exercer", autorisation_exercer)
        await save_group("agrement_dirigeant", agrement_dirigeant)
        await save_group("registre_personnel", registre_personnel)
        await save_group("registre_controles_internes", registre_controles_internes)
        await save_group("extrait_kbis", extrait_kbis)
        await save_group("statuts_entreprise", statuts_entreprise)
        await save_group("justificatifs_dpae", justificatifs_dpae)

        # Sauver l’URL si fournie
        if website_url:
            (base / "site_url.txt").write_text(website_url.strip(), encoding="utf-8")

        return JSONResponse({
            "status": "ok",
            "company": company_name,
            "upload_folder": str(base),
            "files_saved": saved,
            "website_url": website_url or None
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Erreur de téléversement: {e}")
