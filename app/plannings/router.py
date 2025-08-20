# app/plannings/router.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import io, os, time, json

from app.plannings.config import SETTINGS, RuleSettings
from app.plannings.ingest import load_schedule
from app.plannings.analysis import analyze
from app.plannings.export_pdf import export_pdf

# IMPORTANT : définir le router avant d'utiliser @router.*
router = APIRouter(prefix="", tags=["planning-audit"])

@router.get("/planning/health")
def health():
    return {"status": "ok", "rules": SETTINGS.rules.dict()}

@router.get("/planning/rules")
def get_rules():
    return SETTINGS.rules.dict()

@router.put("/planning/rules")
def update_rules(payload: dict):
    try:
        new_rules = RuleSettings(**{**SETTINGS.rules.dict(), **payload})
        SETTINGS.rules = new_rules
        return {"ok": True, "rules": new_rules.dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/planning/analyze")
async def post_analyze(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = load_schedule(content, file.filename)
        result = analyze(df)
        return JSONResponse(content=json.loads(result.model_dump_json()))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/planning/export/report")
async def post_export_report(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = load_schedule(content, file.filename)
        result = analyze(df)

        # Génère un PDF sur disque puis le renvoie (OK sur Render)
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out_path = os.path.join(reports_dir, f"rapport_audit_{int(time.time())}.pdf")
        export_pdf(result, out_path)
        with open(out_path, "rb") as f:
            pdf_bytes = f.read()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="rapport_audit.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
