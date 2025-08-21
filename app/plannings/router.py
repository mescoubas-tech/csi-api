from __future__ import annotations

import io, os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from .ingest import load_schedule  # fonction de lecture CSV/XLSX/PDF numérique

router = APIRouter(prefix="/planning", tags=["planning-audit"])

ALLOWED_EXT = {".csv", ".xlsx", ".xls", ".pdf"}
MAX_SIZE = 25 * 1024 * 1024
REQUIRED_COLS = ["agent_id", "date", "start", "end"]

# ------------------------
# Utils
# ------------------------
def _ext_ok(fname: str) -> bool:
    return os.path.splitext(fname.lower())[1] in ALLOWED_EXT

def _validate_df(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Colonnes manquantes: {missing}. Colonnes trouvées: {list(df.columns)}")

def _parse_dt(d: str, t: str) -> datetime:
    d, t = str(d).strip(), str(t).strip()
    try:
        return datetime.fromisoformat(f"{d} {t}")
    except Exception:
        pass
    try:
        return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
    except Exception:
        raise ValueError(f"Impossible de parser date={d} time={t}")

def _compute_alerts(df: pd.DataFrame) -> Dict[str, Any]:
    alerts = []
    durations = []
    for _, r in df.iterrows():
        try:
            s = _parse_dt(r["date"], r["start"])
            e = _parse_dt(r["date"], r["end"])
            if e < s:
                e += timedelta(days=1)
            dur = (e - s).total_seconds() / 3600
        except Exception:
            dur = None
        durations.append(dur)
        if dur and dur > 10:
            alerts.append({"type":"DAILY_DURATION","agent_id":r["agent_id"],"date":r["date"],"duration":dur})
    df["duration_h"] = durations
    summary = {
        "rows": len(df),
        "agents": df["agent_id"].nunique(),
        "total_hours": round(float(pd.to_numeric(df["duration_h"], errors="coerce").sum() or 0),2)
    }
    return {"summary":summary,"alerts":alerts}

def _make_pdf(analysis: Dict[str,Any]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100,800,"Rapport audit plannings")
    c.drawString(100,780,f"Résumé: {analysis.get('summary')}")
    for i,a in enumerate(analysis.get("alerts",[])[:20]):
        c.drawString(100,760-i*15,str(a))
    c.save()
    return buf.getvalue()

# ------------------------
# Endpoints
# ------------------------
@router.get("/health")
def health() -> Dict[str,str]:
    return {"status":"ok","module":"planning"}

@router.post("/analyze")
async def analyze(file: UploadFile=File(...)) -> JSONResponse:
    if not _ext_ok(file.filename):
        raise HTTPException(400,"Format non supporté")
    data = await file.read()
    if len(data)>MAX_SIZE:
        raise HTTPException(400,"Fichier trop volumineux (>25Mo)")
    df = load_schedule(data,file.filename)
    _validate_df(df)
    return JSONResponse(_compute_alerts(df))

@router.post("/export/report")
async def export_report(file: UploadFile=File(...)) -> StreamingResponse:
    if not _ext_ok(file.filename):
        raise HTTPException(400,"Format non supporté")
    data = await file.read()
    if len(data)>MAX_SIZE:
        raise HTTPException(400,"Fichier trop volumineux (>25Mo)")
    df = load_schedule(data,file.filename)
    _validate_df(df)
    pdf = _make_pdf(_compute_alerts(df))
    headers = {"Content-Disposition":'attachment; filename="rapport.pdf"'}
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers=headers)
