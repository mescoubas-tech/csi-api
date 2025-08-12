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
    with open(get_settings().RULES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])


def _rules_by_id():
    return {r["id"]: r for r in _load_rules()}


def _get_analyzer() -> Analyzer:
    rules = _load_rules()
    learning = LearningDB()
    return Analyzer(rules, learning)


@router.post("/", response_model=AnalysisResult)
async def analyze_file(
    file: UploadFile = File(...),
    export_pdf: Optional[bool] = Form(False)
):
    try:
        tmp_path = os.path.join(get_settings().LEARNING_DB)  # dossier data
        base_dir = os.path.dirname(tmp_path)
        os.makedirs(base_dir, exist_ok=True)

        save_path = os.path.join(base_dir, f"upload_{file.filename}")
        with open(save_path, "wb") as f_out:
            f_out.write(await file.read())

        analyzer = _get_analyzer()
        result = analyzer.analyze_file(save_path)

        if export_pdf:
            pdf_path = os.path.join(
                base_dir,
                f"report_{os.path.splitext(os.path.basename(save_path))[0]}.pdf"
            )
            analyzer.
