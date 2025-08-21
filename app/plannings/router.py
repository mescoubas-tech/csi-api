# app/plannings/router.py
from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List

import pandas as pd
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# Lecture robuste des fichiers (CSV/XLSX/PDF natif)
from .ingest import load_schedule

router = APIRouter(tags=["planning"])


# ----------------------------- Règles & Analyse -----------------------------

def _parse_time(value: str) -> datetime.time | None:
    """Accepte 8:00, 08h00, 08:00, 8.0 … -> time | None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("h", ":").replace("H", ":")
    try:
        # formats usuels
        for fmt in ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f", "%H.%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except Exception:
                pass
        # 8 ou 08
        if s.isdigit():
            h = int(s)
            return datetime.strptime(f"{h:02d}:00", "%H:%M").time()
    except Exception:
        return None
    return None


def _parse_date(value: str) -> datetime.date | None:
    """Tolérant sur les formats de dates."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    # Si c'est déjà un datetime/date (excel), convertir
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date()
    try:
        # formats fréquents
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
    except Exception:
        return None
    return None


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Essaie de retrouver des colonnes standards:
      - agent (nom/prénom / matricule)
      - date (jour)
      - start (heure début)
      - end (heure fin)
    """
    # normaliser noms de colonnes
    cols_map = {c: str(c).strip().lower() for c in df.columns}
    df.columns = [cols_map[c] for c in df.columns]

    def find_col(candidates: List[str]) -> str | None:
        for c in df.columns:
            for want in candidates:
                if want in c:
                    return c
        return None

    col_agent = find_col(["agent", "salari", "employ", "matricule", "nom"])
    col_date = find_col(["date", "jour"])
    col_start = find_col(["debut", "début", "start", "heure debut", "hdebut", "debut poste"])
    col_end = find_col(["fin", "end", "heure fin", "hfin", "fin poste"])

    if col_agent is None or col_date is None or col_start is None or col_end is None:
        # On essaie une heuristique pour les 4 premières colonnes si le tableau est basique
        if df.shape[1] >= 4:
            col_agent = col_agent or df.columns[0]
            col_date = col_date or df.columns[1]
            col_start = col_start or df.columns[2]
            col_end = col_end or df.columns[3]
        else:
            raise ValueError(
                "Colonnes introuvables. Assurez-vous que le tableau contient au moins "
                "les informations Agent/Date/Heure début/Heure fin."
            )

    out = pd.DataFrame(
        {
            "agent": df[col_agent].astype(str),
            "date_raw": df[col_date],
            "start_raw": df[col_start],
            "end_raw": df[col_end],
        }
    )

    # parsing date / heures
    out["date"] = out["date_raw"].apply(_parse_date)
    out["start_t"] = out["start_raw"].apply(_parse_time)
    out["end_t"] = out["end_raw"].apply(_parse_time)

    # lignes valides uniquement
    out = out.dropna(subset=["agent", "date", "start_t", "end_t"]).copy()

    # construire des datetimes
    out["start_dt"] = out.apply(
        lambda r: datetime.combine(r["date"], r["start_t"]), axis=1
    )
    out["end_dt"] = out.apply(
        lambda r: datetime.combine(r["date"], r["end_t"]), axis=1
    )
    # si fin < début (nuit), on ajoute 1 jour
    out.loc[out["end_dt"] <= out["start_dt"], "end_dt"] += timedelta(days=1)

    # durée en heures
    out["hours"] = (out["end_dt"] - out["start_dt"]).dt.total_seconds() / 3600.0
    return out[["agent", "start_dt", "end_dt", "hours", "date"]].sort_values(["agent", "start_dt"]).reset_index(drop=True)


def check_compliance(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Analyse simple :
      - Repos quotidien minimal 11h entre deux postes consécutifs d’un même agent
      - Repos hebdomadaire : max 48h travaillées sur 7 jours glissants
    Renvoie un dict { "errors": [...], "warnings": [...] }.
    """
    table = _normalize_dataframe(df)
    errors: List[str] = []
    warnings: List[str] = []

    # 1) Repos quotidien
    for agent, grp in table.groupby("agent"):
        prev_end = None
        for _, row in grp.iterrows():
            if prev_end is not None:
                rest_h = (row["start_dt"] - prev_end).total_seconds() / 3600.0
                if rest_h < 11.0:
                    errors.append(
                        f"{agent} : repos quotidien insuffisant ({rest_h:.1f} h) "
                        f"entre {prev_end.strftime('%d/%m %H:%M')} et {row['start_dt'].strftime('%d/%m %H:%M')}"
                    )
            prev_end = row["end_dt"]

    # 2) 48h par semaine roulante (7 jours)
    table["week_window_start"] = table["start_dt"] - pd.to_timedelta(6, unit="D")
    # pour chaque ligne, on calcule la somme des heures sur [start-6j ; start]
    for idx, row in table.iterrows():
        mask = (table["agent"] == row["agent"]) & (table["start_dt"] >= row["week_window_start"]) & (table["start_dt"] <= row["start_dt"])
        total = table.loc[mask, "hours"].sum()
        if total > 48.0:
            warnings.append(
                f"{row['agent']} : {total:.1f} h sur 7 jours glissants autour du {row['start_dt'].date().strftime('%d/%m/%Y')} (> 48 h)"
            )

    return {"errors": errors, "warnings": warnings}


# ----------------------------- Rendu HTML & PDF -----------------------------

def render_html_report(findings: Dict[str, List[str]], filename: str) -> str:
    errors = findings.get("errors", [])
    warnings = findings.get("warnings", [])

    def li(items: List[str]) -> str:
        if not items:
            return '<li class="muted">Aucun</li>'
        return "".join(f"<li>{x}</li>" for x in items)

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Analyse des plannings — {filename}</title>
<style>
  :root {{
    --bg: #0b0b0c; --fg:#f7f7f7; --muted:#a1a1aa; --card:#111214; --accent:#3b82f6;
    --bad:#ef4444; --warn:#f59e0b; --ok:#22c55e;
    --radius:16px;
  }}
  html,body {{ background:var(--bg); color:var(--fg); font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width: 960px; margin: 48px auto; padding: 0 20px; }}
  h1 {{ font-size: 28px; margin: 0 0 12px; }}
  .muted {{ color: var(--muted); }}
  .card {{ background:var(--card); border-radius:var(--radius); padding:20px; margin:16px 0; }}
  .pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; vertical-align:middle; margin-left:8px; }}
  .pill.err {{ background: color-mix(in oklab, var(--bad) 20%, transparent); color: var(--bad); border:1px solid var(--bad); }}
  .pill.warn {{ background: color-mix(in oklab, var(--warn) 20%, transparent); color: var(--warn); border:1px solid var(--warn); }}
  ul {{ margin: 8px 0 0 20px; }}
  footer {{ margin-top:24px; font-size:13px; color:var(--muted); }}
</style>
<div class="wrap">
  <h1>Analyse des plannings</h1>
  <div class="muted">Fichier : {filename}</div>

  <div class="card">
    <h2>Manquements <span class="pill err">{len(errors)}</span></h2>
    <ul>{li(errors)}</ul>
  </div>

  <div class="card">
    <h2>Points de vigilance <span class="pill warn">{len(warnings)}</span></h2>
    <ul>{li(warnings)}</ul>
  </div>

  <footer>
    Références (exemples) : repos quotidien minimal de 11 heures (directive 2003/88/CE; art. L3131-1 s.), durée hebdomadaire maximale 48 h (L3121-20 s.).<br>
    Ce rapport est indicatif, à valider selon vos accords collectifs et spécificités.
  </footer>
</div>
"""


def _build_pdf(findings: Dict[str, List[str]], filename: str) -> bytes:
    """Génère un PDF simple avec reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "Analyse des plannings")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Fichier : {filename}")
    y -= 1.0 * cm

    def draw_block(title: str, items: List[str]):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, title)
        y -= 0.6 * cm
        c.setFont("Helvetica", 10)
        if not items:
            c.drawString(2.5 * cm, y, "- Aucun")
            y -= 0.5 * cm
        else:
            for it in items:
                if y < 2 * cm:
                    c.showPage()
                    y = h - 2 * cm
                    c.setFont("Helvetica", 10)
                c.drawString(2.5 * cm, y, f"- {it}")
                y -= 0.5 * cm
        y -= 0.3 * cm

    draw_block("Manquements", findings.get("errors", []))
    draw_block("Points de vigilance", findings.get("warnings", []))

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        2 * cm,
        1.5 * cm,
        "Références indicatives : repos quotidien 11 h (dir. 2003/88/CE), 48 h / semaine (L3121-20 s.)."
    )

    c.showPage()
    c.save()
    return buf.getvalue()


# ----------------------------- Endpoints -----------------------------

@router.get("/planning/health")
async def health() -> dict:
    return {"ok": True}


@router.post("/planning/analyze")
async def analyze_planning_json(file: UploadFile = File(...)) -> JSONResponse:
    """Retour JSON des constats."""
    try:
        df = await load_schedule(file)
        findings = check_compliance(df)
        return JSONResponse(findings, status_code=200)
    except ValueError as ve:
        return JSONResponse({"detail": str(ve)}, status_code=400)
    except Exception as e:
        return JSONResponse({"detail": f"Analyse impossible: {e}"}, status_code=500)


@router.post("/planning/analyze/html", response_class=HTMLResponse)
async def analyze_planning_html(file: UploadFile = File(...)) -> HTMLResponse:
    """
    Retourne une page HTML lisible avec les manquements détectés.
    Garde-fous & messages explicites.
    """
    try:
        df = await load_schedule(file)  # robust loader
        findings = check_compliance(df)
        html = render_html_report(findings, filename=(file.filename or "planning"))
        return HTMLResponse(content=html, status_code=200)

    except ValueError as ve:
        msg = str(ve)
        html = f"""
        <!doctype html><meta charset="utf-8">
        <title>Analyse des plannings — erreur</title>
        <style>
          body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:32px;color:#111}}
          pre{{background:#111;color:#fff;padding:16px;border-radius:12px;white-space:pre-wrap}}
          .muted{{color:#666}}
        </style>
        <h1>Analyse des plannings</h1>
        <p class="muted">Impossible d’analyser le fichier.</p>
        <pre>{msg}</pre>
        """
        return HTMLResponse(content=html, status_code=400)

    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        html = f"""
        <!doctype html><meta charset="utf-8">
        <title>Analyse des plannings — erreur inattendue</title>
        <style>
          body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:32px;color:#111}}
          pre{{background:#111;color:#fff;padding:16px;border-radius:12px;white-space:pre-wrap}}
          .muted{{color:#666}}
        </style>
        <h1>Analyse des plannings</h1>
        <p class="muted">Une erreur inattendue est survenue.</p>
        <pre>{msg}</pre>
        """
        return HTMLResponse(content=html, status_code=500)


@router.post("/planning/export/report")
async def export_planning_report(file: UploadFile = File(...)) -> StreamingResponse:
    """
    Génère un PDF synthétique des constats (plannings).
    """
    try:
        df = await load_schedule(file)
        findings = check_compliance(df)
        pdf_bytes = _build_pdf(findings, filename=(file.filename or "planning"))
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="rapport_audit_plannings.pdf"'},
        )
    except ValueError as ve:
        return JSONResponse({"detail": str(ve)}, status_code=400)
    except Exception as e:
        return JSONResponse({"detail": f"Export impossible: {e}"}, status_code=500)
