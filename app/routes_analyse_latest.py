# app/routes_analyze_latest.py
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import re

router = APIRouter()

# base locale où tu sauvegardes les uploads
UPLOAD_BASE = Path("data/uploads")  # <= correspond à ".../src/data/uploads"

PLANNING_PATTERNS = re.compile(r"(planning|plannings|rota|schedule)", re.I)

@router.get("/analyze-latest")
def analyze_latest(company: str = Query(..., min_length=1)):
    base = Path(__file__).resolve().parent.parent / UPLOAD_BASE  # => app/..../data/uploads
    if not base.exists():
        raise HTTPException(404, f"Upload base not found: {base}")

    # Dossiers du type "Company_YYYYmmdd_HHMMSS"
    dirs = sorted(
        [p for p in base.glob(f"{company}_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not dirs:
        raise HTTPException(404, f"Aucun upload trouvé pour '{company}'")

    folder = dirs[0]
    pdfs = list(folder.rglob("*.pdf"))

    if not pdfs:
        return {
            "message": "Aucune pièce détectée",
            "folder": str(folder),
            "pieces_detectees": [],
            "plannings_detectes": []
        }

    plannings = [str(p) for p in pdfs if PLANNING_PATTERNS.search(p.name)]
    autres = [str(p) for p in pdfs if str(p) not in plannings]

    return {
        "message": "OK",
        "company": company,
        "folder": str(folder),
        "total_pdfs": len(pdfs),
        "plannings_detectes": plannings,
        "pieces_detectees": autres
    }
