# app/routes_analyze.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging

router = APIRouter()
log = logging.getLogger("app")
UPLOAD_ROOT = Path("/tmp/uploads")

class AnalyzeIn(BaseModel):
    session_id: str
    file_ids: list[str] | None = None

@router.post("/analyze")
def analyze(inp: AnalyzeIn):
    folder = UPLOAD_ROOT / inp.session_id
    files = []
    if inp.file_ids:
        files = [folder / fid for fid in inp.file_ids if (folder / fid).exists()]
    else:
        files = list(folder.glob("*.pdf"))

    files = [p for p in files if p.exists()]
    log.info(f"[ANALYZE] session={inp.session_id} files_in={inp.file_ids} files_found={[str(p) for p in files]}")

    if not files:
        return {"pieces_detectees": [], "plannings_detectes": [], "message": "Aucune pièce détectée"}

    plannings, autres = [], []
    for p in files:
        name = p.name.lower()
        if any(k in name for k in ["planning", "plannings", "rota", "schedule"]):
            plannings.append(p.name)
        else:
            autres.append(p.name)

    return {
        "message": "OK",
        "pieces_detectees": autres,
        "plannings_detectes": plannings
    }
