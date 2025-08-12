# app/routers/upload.py
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.templating import Jinja2Templates

from ..core.config import get_settings

router = APIRouter(tags=["upload"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

def _safe_name(s: str) -> str:
    s = s.strip().replace(" ", "_")
    return SAFE_CHARS.sub("", s)[:80] or "entreprise"

def _safe_file_name(name: str) -> str:
    base = os.path.basename(name or "")
    return _safe_name(base) or f"file_{int(time.time())}"

def _ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p

def _check_size(buf: bytes):
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    if len(buf) > max_bytes:
        raise HTTPException(413, f"Fichier trop volumineux (> {get_settings().MAX_UPLOAD_MB} Mo)")

ALLOWED_EXTS = {".pdf", ".docx", ".xlsx", ".zip", ".csv"}

def _check_ext(name: str):
    ext = Path(name).suffix.lower()
    if ext and ext not in ALLOWED_EXTS:
        raise HTTPException(415, f"Extension non autorisée: {ext}")

@router.get("/televerser", response_class=HTMLResponse, include_in_schema=False)
def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload")
async def upload_all(
    request: Request,
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
        _ensure_dir(str(base))

        saved: List[str] = []

        async def save_group(name: str, files: List[UploadFile]):
            if not files:
                return
            group_dir = _ensure_dir(str(base / name))
            for f in files:
                content = await f.read()
                _check_size(content)
                safe_name = _safe_file_name(f.filename or "")
                _check_ext(safe_name)
                target = Path(group_dir) / safe_name
                with open(target, "wb") as out:
                    out.write(content)
                saved.append(str(target))

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

        if website_url:
            (base / "site_url.txt").write_text(website_url.strip(), encoding="utf-8")

        return JSONResponse(
            {
                "status": "ok",
                "company": company_name,
                "upload_folder": str(base),
                "files_saved": saved,
                "website_url": website_url or None,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Erreur de téléversement: {e}")
