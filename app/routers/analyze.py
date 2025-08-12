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
