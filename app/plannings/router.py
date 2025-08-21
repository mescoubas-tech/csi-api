from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import io

from .ingest import load_schedule
from .rules import analyze_schedule

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


router = APIRouter(prefix="/planning", tags=["Planning"])


@router.get("/health")
def health():
    return {"status": "ok", "module": "planning"}


@router.post("/analyze")
async def post_analyze(file: UploadFile = File(...)):
    """
    Lit le planning (CSV/XLSX/PDF numérique), normalise et renvoie :
      { summary: {...}, violations: [ ... ] }
    """
    try:
        df = load_schedule(file)
        result = analyze_schedule(df)
        return JSONResponse(result)
    except HTTPException as e:
        raise e
    except Exception as e:  # log minimal
        raise HTTPException(400, f"Analyse impossible: {e}")


def _draw_wrapped(c: canvas.Canvas, text: str, x: int, y: int, max_width: int, line_height=14):
    from textwrap import wrap
    for line in wrap(text, width=max_width):
        c.drawString(x, y, line)
        y -= line_height
    return y


@router.post("/export/report")
async def post_export_report(file: UploadFile = File(...)):
    """
    Génère un PDF synthèse des non-conformités.
    """
    try:
        df = load_schedule(file)
        result = analyze_schedule(df)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(400, f"Export impossible: {e}")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Rapport d'audit des plannings"); y -= 24
    c.setFont("Helvetica", 11)
    s = result["summary"]
    c.drawString(40, y, f"Salariés: {s.get('employees',0)}  |  Jours: {s.get('days',0)}  |  Heures totales: {s.get('total_hours',0)}"); y -= 18
    c.drawString(40, y, f"Non-conformités: {s.get('violations_count',0)}  |  Par type: {s.get('by_code',{})}"); y -= 26

    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Détails des non-conformités"); y -= 20
    c.setFont("Helvetica", 10)
    for v in result["violations"]:
        line = f"[{v['code']}] {v.get('employee_name') or v['employee_id']} — {v['date']} — {v['message']}"
        y = _draw_wrapped(c, line, 40, y, 95, line_height=12)  # largeur approx (car wrap en nb car.)
        if y < 60:
            c.showPage(); y = h - 50; c.setFont("Helvetica", 10)

    c.showPage(); c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=rapport_audit_plannings.pdf"})
