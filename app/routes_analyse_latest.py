import os, re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

_PLANNING_RE = re.compile(r"(planning|plannings|rota|schedule)", re.I)
_UPLOAD_BASE = os.getenv("UPLOAD_BASE", "data/uploads")

def _base_dir() -> Path:
    p = Path(_UPLOAD_BASE)
    return p if p.is_absolute() else (Path.cwd() / p)

@router.get("/analyze-latest")
def analyze_latest(company: str = Query(..., min_length=1)):
    base = _base_dir()
    if not base.exists():
        raise HTTPException(404, f"Upload base not found: {base}")

    # Dossiers type "Company_YYYYmmdd_HHMMSS"
    dirs = sorted(
        [d for d in base.glob(f"{company}_*") if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        raise HTTPException(404, f"Aucun upload trouvé pour '{company}'")

    folder = dirs[0]
    pdfs = list(folder.rglob("*.pdf"))

    plannings = [str(p) for p in pdfs if _PLANNING_RE.search(p.name)]
    autres = [str(p) for p in pdfs if str(p) not in plannings]

    return {
      "message": "OK" if pdfs else "Aucune pièce détectée",
      "company": company,
      "folder": str(folder),
      "total_pdfs": len(pdfs),
      "plannings_detectes": plannings,
      "pieces_detectees": autres,
    }
