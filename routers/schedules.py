# app/routers/schedules.py
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from ..core.config import get_settings
from ..models.schemas import SchedulesCheckResult

router = APIRouter(prefix="/schedules", tags=["schedules"])

@router.post("/check", response_model=SchedulesCheckResult)
async def check(
    files: List[UploadFile] = File([]),
    company_folder: Optional[str] = Form(None),
):
    # Import à l'intérieur pour éviter un crash au démarrage si le service n'est pas encore présent
    try:
        from ..services.schedule_checker import check_schedules
    except Exception as e:
        raise HTTPException(500, f"Module schedule_checker manquant: {e}")

    paths: List[Path] = []

    # Fichiers envoyés directement
    if files:
        tmp = Path(get_settings().PROJECT_ROOT) / "data" / "tmp_plannings"
        tmp.mkdir(parents=True, exist_ok=True)
        for f in files:
            p = tmp / (f.filename or "planning.csv")
            p.write_bytes(await f.read())
            paths.append(p)

    # Ou lecture d’un dossier d’upload existant
    if company_folder:
        base = Path(get_settings().UPLOADS_DIR)
        folder = (base / company_folder).resolve()
        if not str(folder).startswith(str(base.resolve())):
            raise HTTPException(403, "Dossier hors zone autorisée.")
        plan_dir = folder / "plannings_agents_6mois"
        if not plan_dir.exists():
            raise HTTPException(404, f"Dossier introuvable : {plan_dir}")
        for p in plan_dir.glob("**/*"):
            if p.suffix.lower() in (".csv", ".xlsx", ".xlsm"):
                paths.append(p)

    if not paths:
        raise HTTPException(400, "Aucun planning fourni (fichiers ou company_folder).")

    return check_schedules(paths)
