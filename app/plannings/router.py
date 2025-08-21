# routers/plannings.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, AnyHttpUrl
from typing import Any, Dict

from services.plannings_analyzer import analyze_planning_from_url, PlanningAnalysisError

router = APIRouter(prefix="/plannings", tags=["plannings"])

class AnalyzeRequest(BaseModel):
    url: AnyHttpUrl

class AnalyzeResponse(BaseModel):
    success: bool
    data: Dict[str, Any] | None = None
    user_message: str | None = None

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_planning(req: AnalyzeRequest):
    try:
        result = await analyze_planning_from_url(str(req.url))
        return AnalyzeResponse(success=True, data=result)
    except PlanningAnalysisError as exc:
        # On ne remonte plus la page HTML Cloudflare à l’UI
        return AnalyzeResponse(
            success=False,
            user_message=exc.user_message,
        )
    except Exception as exc:
        # Filet de sécurité
        raise HTTPException(status_code=500, detail=f"Erreur interne pendant l'analyse: {exc}")
