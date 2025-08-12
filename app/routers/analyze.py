import os
import yaml
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from ..core.config import get_settings
from ..models.schemas import AnalysisResult, TrainPayload
from ..services.analyzer import Analyzer
from ..services.learning import LearningDB

router = APIRouter(prefix="/analyze", tags=["analyze"])


def _load_rules():
    """Charge les règles depuis le YAML indiqué par RULES_PATH."""
    rules_path = get_settings().RULES_PATH
    if not os.path.exists(rules_path):
        raise HTTPException(500, f"RULES_PATH introuvable: {rules_path}")
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])


def _rules_by_id():
    """Indexe les règles par id pour les MAJ de pondération."""
    return {r["id"]: r for r in _load_rules() if "id" in r}


def _get_data_dir() -> str:
    """
    Détermine un dossier d'écriture valide.
    - Si LEARNING_DB est un dossier, on l'utilise.
    - Si c'est un fichier, on prend son parent.
    - Sinon, fallback sur /tmp/csi-api (Render-friendly).
    """
    p = get_settings().LEARNING_DB
    if p and os.path.isdir(p):
        base_dir = p
    elif p:
        base_dir = os.path.dirname(p) or "/tmp/csi-api"
    else:
        base_dir = "/tmp/csi-api"
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _get_analyzer() -> Analyzer:
    rules = _load_rules()
    learning = LearningDB()
    return Analyzer(rules, learning)


@router.post("/", response_model=AnalysisResult)
async def analyze_file(
    file: UploadFile = File(...),
    export_pdf: Optional[bool] = Form(False),
):
    try:
        base_dir = _get_data_dir()

        # Nom de fichier sûr
        fname = os.path.basename(file.filename).replace(os.sep, "_")
        save_path = os.path.join(base_dir, f"upload_{fname}")

        # Sauvegarde du fichier uploadé
        content = await file.read()
        with open(save_path, "wb") as f_out:
            f_out.write(content)

        analyzer = _get_analyzer()
        result = analyzer.analyze_file(save_path)

        if export_pdf:
            pdf_name = f"report_{os.path.splitext(os.path.basename(save_path))[0]}.pdf"
            pdf_path = os.path.join(base_dir, pdf_name)
            analyzer.export_pdf(result, pdf_path)

            # Ajoute le chemin du PDF au retour
            if hasattr(result, "model_dump"):
                rd = result.model_dump()
            else:
                rd = dict(result) if isinstance(result, dict) else {"result": str(result)}
            rd["report_pdf_path"] = pdf_path
            return rd

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Erreur d'analyse: {e}")


@router.post("/train")
async def train(payload: TrainPayload):
    learning = LearningDB()
    learning.update_with_feedback([fb.model_dump() for fb in payload.feedback])
    rb = _rules_by_id()
    for fb in payload.feedback:
        r = rb.get(fb.rule_id)
        if r:
            learning.update_category_weight(r.get("category", "Général"), fb.correct)
    return {"status": "updated", "count": len(payload.feedback)}


@router.get("/report")
def download_report(path: str):
    """Télécharge un PDF généré, restreint au data dir."""
    base_dir = _get_data_dir()
    real = os.path.realpath(path)
    base_real = os.path.realpath(base_dir)
    if not real.startswith(base_real + os.sep):
        raise HTTPException(403, "Accès refusé")
    if not os.path.exists(real):
        raise HTTPException(404, "Fichier non trouvé")
    return FileResponse(real, filename=os.path.basename(real), media_type="application/pdf")
