from __future__ import annotations

import io
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from .ingest import load_schedule  # lecture CSV/XLSX/PDF numérique

router = APIRouter(prefix="/planning", tags=["planning-audit"])

# --------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------
ALLOWED_EXT = {".csv", ".xlsx", ".xls", ".pdf"}
MAX_SIZE = 25 * 1024 * 1024  # 25 Mo

REQUIRED_COLS = ["agent_id", "date", "start", "end"]
OPTIONAL_COLS = [
    "pause_min",
    "nom",
    "prenom",
    "site",
    "employer",
    "has_derogation_daily_12h",
    "is_minor",
    "is_night_worker",
]

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXT


def _validate_dataframe(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes minimales manquantes: {missing}. Colonnes trouvées: {list(df.columns)}",
        )


def _parse_dt(date_str: str, time_str: str) -> datetime:
    # essaye plusieurs formats horaires usuels
    time_str = str(time_str).strip()
    date_str = str(date_str).strip()
    for tf in ("%H:%M", "%Hh%M", "%H.%M", "%H:%M:%S"):
        try:
            return datetime.fromisoformat(date_str) + timedelta(
                hours=int(time_str[:2]), minutes=int(time_str[-2:])
            )
        except Exception:
            pass
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", f"%Y-%m-%d {tf}")
            return dt
        except Exception:
            continue
    # dernier recours : si date au bon format et heure "HH"
    try:
        h = int(time_str)
        return datetime.fromisoformat(date_str) + timedelta(hours=h)
    except Exception as e:
        raise ValueError(f"Horodatage invalide: date='{date_str}', heure='{time_str}'") from e


def _compute_alerts(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Règles simples illustratives :
    - durée journalière > 10h → alerte (sauf has_derogation_daily_12h True → seuil 12h)
    - pause minimale 20 min si durée >= 6h
    - repos quotidien < 11h entre deux jours consécutifs d’un même agent
    - durée hebdo > 48h (somme glissante simple par semaine civile)
    """
    alerts: List[Dict[str, Any]] = []

    # durée journalière
    durations = []
    for i, row in df.iterrows():
        try:
            start_dt = _parse_dt(str(row["date"]), str(row["start"]))
            end_dt = _parse_dt(str(row["date"]), str(row["end"]))
            if end_dt < start_dt:
                # Passage minuit
                end_dt += timedelta(days=1)
            dur = (end_dt - start_dt).total_seconds() / 3600.0
        except Exception:
            dur = None

        durations.append(dur)

        if dur is not None:
            has_derog = bool(row.get("has_derogation_daily_12h", False))
            limit = 12.0 if has_derog else 10.0
            if dur > limit:
                alerts.append(
                    {
                        "type": "DAILY_DURATION",
                        "agent_id": row["agent_id"],
                        "date": row["date"],
                        "duration_h": round(dur, 2),
                        "limit_h": limit,
                        "message": f"Durée journalière {dur:.2f}h > {limit}h",
                    }
                )

            # pause
            pause_min = int(row.get("pause_min", 0) or 0)
            if dur >= 6.0 and pause_min < 20:
                alerts.append(
                    {
                        "type": "DAILY_BREAK",
                        "agent_id": row["agent_id"],
                        "date": row["date"],
                        "pause_min": pause_min,
                        "required_min": 20,
                        "message": "Pause insuffisante (< 20 min pour journée ≥ 6h)",
                    }
                )

    df = df.copy()
    df["duration_h"] = durations

    # repos quotidien (11h mini) — tri par agent/date
    try:
        df_sorted = df.sort_values(["agent_id", "date", "start"])
        for agent, g in df_sorted.groupby("agent_id"):
            prev_end: datetime | None = None
            prev_date: str | None = None
            for _, r in g.iterrows():
                try:
                    s = _parse_dt(str(r["date"]), str(r["start"]))
                    e = _parse_dt(str(r["date"]), str(r["end"]))
                    if e < s:
                        e += timedelta(days=1)
                except Exception:
                    continue

                if prev_end is not None:
                    rest_h = (s - prev_end).total_seconds() / 3600.0
                    if rest_h < 11.0:
                        alerts.append(
                            {
                                "type": "DAILY_REST",
                                "agent_id": agent,
                                "prev_date": prev_date,
                                "date": r["date"],
                                "rest_h": round(rest_h, 2),
                                "required_h": 11.0,
                                "message": f"Repos quotidien {rest_h:.2f}h < 11h",
                            }
                        )
                prev_end = e
                prev_date = r["date"]
    except Exception:
        # on ne bloque pas l’analyse si un agent a des données incompletes
        pass

    # durée hebdo > 48h
    try:
        tmp = df.copy()
        # semaine civile simple à partir de la date
        tmp["week"] = pd.to_datetime(tmp["date"]).dt.isocalendar().week
        week_sum = (
            tmp.groupby(["agent_id", "week"])["duration_h"].sum(min_count=1).reset_index()
        )
        for _, r in week_sum.iterrows():
            if pd.notna(r["duration_h"]) and r["duration_h"] > 48.0:
                alerts.append(
                    {
                        "type": "WEEKLY_DURATION",
                        "agent_id": r["agent_id"],
                        "week": int(r["week"]),
                        "duration_h": round(float(r["duration_h"]), 2),
                        "limit_h": 48.0,
                        "message": f"Durée hebdomadaire {float(r['duration_h']):.2f}h > 48h",
                    }
                )
    except Exception:
        pass

    by_agent = (
        df.groupby("agent_id")["duration_h"].sum(min_count=1).fillna(0).to_dict()
    )

    summary = {
        "rows": int(len(df)),
        "agents": int(df["agent_id"].nunique()),
        "total_hours": round(float(pd.to_numeric(df["duration_h"], errors="coerce").sum() or 0), 2),
        "period_min": str(pd.to_datetime(df["date"]).min()) if "date" in df.columns else None,
        "period_max": str(pd.to_datetime(df["date"]).max()) if "date" in df.columns else None,
    }

    return {"summary": summary, "alerts": alerts, "by_agent": by_agent}


def _make_pdf_report(analysis: Dict[str, Any]) -> bytes:
    """Génère un PDF simple à partir des résultats."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    y = h - 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "Rapport d’audit – Plannings")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)

    summary = analysis.get("summary", {})
    c.drawString(2 * cm, y, f"Lignes: {summary.get('rows', 0)}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Agents: {summary.get('agents', 0)}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Heures totales: {summary.get('total_hours', 0)} h")
    y -= 0.7 * cm

    alerts = analysis.get("alerts", [])
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, f"Alerte(s): {len(alerts)}")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)

    if alerts:
        for a in alerts[:40]:  # limite d’affichage
            line = f"- {a.get('type')}: {a.get('message')} (agent={a.get('agent_id')})"
            if y < 2 * cm:
                c.showPage()
                y = h - 2 * cm
                c.setFont("Helvetica", 9)
            c.drawString(2 * cm, y, line[:110])
            y -= 0.45 * cm
    else:
        c.drawString(2 * cm, y, "Aucune alerte détectée.")

    c.showPage()
    c.save()
    return buffer.getvalue()

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------
@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "module": "planning", "allowed": sorted(list(ALLOWED_EXT))}


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> JSONResponse:
    # Validation basique
    if not _ext_ok(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Format non supporté (utiliser .csv, .xlsx, .xls ou .pdf)",
        )

    # Lire en mémoire
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (> 25 Mo).")

    try:
        df = load_schedule(content, file.filename)
        _validate_dataframe(df)
        result = _compute_alerts(df)
        return JSONResponse(result)
    except HTTPException:
        # relancer intact
        raise
    except Exception as e:
        # message clair si PDF scanné
        msg = str(e)
        if "Aucun tableau détecté" in msg:
            raise HTTPException(
                status_code=400,
                detail="PDF non exploitable (probablement scanné/image). Fournir un PDF numérique (texte sélectionnable) ou un CSV/XLSX.",
            )
        raise HTTPException(status_code=400, detail=msg)


@router.post("/export/report")
async def export_report(file: UploadFile = File(...)) -> StreamingResponse:
    if not _ext_ok(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Format non supporté (utiliser .csv, .xlsx, .xls ou .pdf)",
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (> 25 Mo).")

    try:
        df = load_schedule(content, file.filename)
        _validate_dataframe(df)
        analysis = _compute_alerts(df)
        pdf_bytes = _make_pdf_report(analysis)
        headers = {"Content-Disposition": 'attachment; filename="rapport_audit_plannings.pdf"'}
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "Aucun tableau détecté" in msg:
            raise HTTPException(
                status_code=400,
                detail="PDF non exploitable (probablement scanné/image). Fournir un PDF numérique (texte sélectionnable) ou un CSV/XLSX.",
            )
        raise HTTPException(status_code=400, detail=msg)
