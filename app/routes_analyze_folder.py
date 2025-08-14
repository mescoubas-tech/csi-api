from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re

router = APIRouter()
_PLANNING_RE = re.compile(r"(planning|plannings|rota|schedule)", re.I)

class Inp(BaseModel):
    upload_folder: str

@router.post("/analyze-by-folder")
def analyze_by_folder(inp: Inp):
    folder = Path(inp.upload_folder)
    if not folder.exists():
        raise HTTPException(404, f"Dossier introuvable: {folder}")

    pdfs = list(folder.rglob("*.pdf"))
    plannings = [str(p) for p in pdfs if _PLANNING_RE.search(p.name)]
    autres = [str(p) for p in pdfs if str(p) not in plannings]

    return {
      "message": "OK" if pdfs else "Aucune pièce détectée",
      "folder": str(folder),
      "total_pdfs": len(pdfs),
      "plannings_detectes": plannings,
      "pieces_detectees": autres,
    }
