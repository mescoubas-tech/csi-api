from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .ingest import load_schedule          # Lecture & normalisation (CSV/XLSX/PDF numérique)
from .rules import analyze_schedule        # Application des règles & calcul des violations


# --------------------------------------------------------------------
# Templates (HTML) : dossier app/templates
# --------------------------------------------------------------------
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --------------------------------------------------------------------
# Router
# --------------------------------------------------------------------
router = APIRouter(prefix="/planning", tags=["Planning"])


@router.get("/health")
def health():
    return {"status": "ok", "module": "planning"}


# --------------------------------------------------------------------
# Analyse JSON
# --------------------------------------------------------------------
@router.post("/analyze")
async def post_analyze(file: UploadFile = File(...)):
    """
    Lit le planning (CSV / XLSX / PDF numérique avec tableaux), normalise et renvoie :
      {
        "summary": { employees, days, total_hours, violations_count, by_code },
        "violations": [
            { employee_id, employee_name, date, code, message, details }
        ]
      }
    """
    try:
        df = load_schedule(file)
        result = analyze_schedule(df)
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analyse impossible: {e}")


# --------------------------------------------------------------------
# Analyse HTML (page dédiée)
# --------------------------------------------------------------------
@router.post("/analyze/html", response_class=HTMLResponse)
async def analyze_html(request: Request, file: UploadFile = File(...)):
    """
    Version 'plein écran' : lance l'analyse et rend une page HTML lisible
    avec résumé + liste des non-conformités + références légales.
    """
    try:
        df = load_schedule(file)
        result = analyze_schedule(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analyse impossible: {e}")

    ctx = {
        "request": request,
        "title": "Analyse des plannings",
        "result": result,
    }
    return templates.TemplateResponse("planning_report.html", ctx)


# --------------------------------------------------------------------
# Export PDF (rapport synthèse)
# --------------------------------------------------------------------
def _draw_wrapped(c: canvas.Canvas, text: str, x: int, y: int, max_chars: int, line_height: int = 12) -> int:
    """
    Petit wrap "caractères" (approx.) pour reporter une ligne trop longue sur plusieurs lignes.
    max_chars n'est pas des pixels mais un nombre approximatif de caractères par ligne.
    """
    from textwrap import wrap
    for line in wrap(text, width=max_chars):
        c.drawString(x, y, line)
        y -= line_height
    return y


@router.post("/export/report")
async def post_export_report(file: UploadFile = File(...)):
    """
    Génère un PDF synthèse des non-conformités sur base du même fichier planning.
    """
    try:
        df = load_schedule(file)
        result = analyze_schedule(df)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export impossible: {e}")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    y = h - 50

    # En-tête
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Rapport d'audit des plannings"); y -= 24

    # Résumé
    c.setFont("Helvetica", 11)
    s = result.get("summary", {})
    c.drawString(40, y, f"Salariés: {s.get('employees',0)}  |  Jours: {s.get('days',0)}  |  Heures totales: {s.get('total_hours',0)}"); y -= 18
    c.drawString(40, y, f"Non-conformités: {s.get('violations_count',0)}  |  Par type: {s.get('by_code',{})}"); y -= 26

    # Détails
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Détails des non-conformités"); y -= 20
    c.setFont("Helvetica", 10)

    for v in result.get("violations", []):
        who = v.get("employee_name") or v.get("employee_id")
        line = f"[{v.get('code','?')}] {who} — {v.get('date','-')} — {v.get('message','')}"
        y = _draw_wrapped(c, line, 40, y, max_chars=95, line_height=12)
        if y < 60:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)

    # Références légales (pied de page)
    if y < 120:
        c.showPage()
        y = h - 50
        c.setFont("Helvetica", 10)

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Références (Code du travail)"); y -= 16
    c.setFont("Helvetica", 10)
    refs = [
        "Repos quotidien ≥ 11 h — L3131-1.",
        "Repos hebdomadaire (≈ 35 h : 24 h + 11 h) — L3132-2 (et rappel du repos quotidien).",
        "Durée quotidienne maximale 10 h (dérogations possibles) — L3121-18.",
        "Durée hebdomadaire maximale 48 h et moyenne 44 h sur 12 semaines — L3121-20 et L3121-22.",
    ]
    for r in refs:
        y = _draw_wrapped(c, f"- {r}", 40, y, max_chars=95, line_height=12)
        if y < 60:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rapport_audit_plannings.pdf"},
    )
