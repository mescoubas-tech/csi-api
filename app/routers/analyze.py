import os
import yaml
import inspect
from importlib import import_module
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from ..core.config import get_settings
from ..models.schemas import AnalysisResult, TrainPayload

# Import robuste de Analyzer
_analyzer_mod = import_module("app.services.analyzer")
Analyzer = getattr(_analyzer_mod, "Analyzer", None)
if Analyzer is None:
    # trouve une classe dont le nom finit par 'Analyzer'
    candidates = [
        obj for name, obj in inspect.getmembers(_analyzer_mod, inspect.isclass)
        if name.lower().endswith("analyzer")
    ]
    if not candidates:
        raise ImportError("Aucune classe 'Analyzer' (ou équivalent) trouvée dans app.services.analyzer")
    Analyzer = candidates[0]

from ..services.learning import LearningDB
def _get_data_dir() -> str:
    # 1) Si LEARNING_DB est un dossier, on l'utilise
    # 2) Si c'est un fichier -> on prend son parent
    # 3) Sinon fallback /tmp/csi-api
    p = get_settings().LEARNING_DB
    if p and os.path.isdir(p):
        base_dir = p
    elif p:
        base_dir = os.path.dirname(p) or "/tmp/csi-api"
    else:
        base_dir = "/tmp/csi-api"
    os.makedirs(base_dir, exist_ok=True)
    return base_dir
    @router.post("/", response_model=AnalysisResult)
async def analyze_file(file: UploadFile = File(...), export_pdf: Optional[bool] = Form(False)):
    try:
        base_dir = _get_data_dir()
        # nom de fichier simple et sûr
        fname = os.path.basename(file.filename).replace(os.sep, "_")
        save_path = os.path.join(base_dir, f"upload_{fname}")
        with open(save_path, "wb") as f_out:
            f_out.write(await file.read())

        analyzer = _get_analyzer()
        result = analyzer.analyze_file(save_path)

        if export_pdf:
            pdf_name = f"report_{os.path.splitext(os.path.basename(save_path))[0]}.pdf"
            pdf_path = os.path.join(base_dir, pdf_name)
            analyzer.export_pdf(result, pdf_path)

            # si response_model=AnalysisResult, renvoie un objet AnalysisResult
            # et expose la route /report pour le téléchargement
            rd = result.model_dump()
            rd["report_pdf_path"] = pdf_path
            return rd  # ou ajuste le modèle pour inclure ce champ

        return result
    except Exception as e:
        raise HTTPException(400, f"Erreur d'analyse: {e}")
