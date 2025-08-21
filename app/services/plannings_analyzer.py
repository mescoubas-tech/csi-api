# app/services/plannings_analyzer.py
from __future__ import annotations
from typing import Any, Dict, List
import pandas as pd
import httpx

# ✅ importe via 'app.'
from app.services.datetime_utils import ensure_datetimes_pipeline

class PlanningAnalysisError(Exception):
    def __init__(self, user_message: str, technical_detail: str = "", upstream_status: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail
        self.upstream_status = upstream_status

async def _fetch_text(url: str, timeout_s: float = 25.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout_s, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url, follow_redirects=True)
            if r.status_code >= 500:
                raise PlanningAnalysisError(
                    user_message="Le site source des plannings est indisponible (5xx). Réessaie plus tard.",
                    technical_detail=f"status={r.status_code}"
                )
            r.raise_for_status()
            return r.text
    except httpx.HTTPError as e:
        raise PlanningAnalysisError(
            user_message="Impossible de récupérer la page du planning (réseau/timeout).",
            technical_detail=str(e)
        )

def _parse_html_to_dataframe(html: str) -> pd.DataFrame:
    # Exemple : 1ère table HTML
    dfs: List[pd.DataFrame] = pd.read_html(html)
    if not dfs:
        raise PlanningAnalysisError("Aucune table planning trouvée dans la page.")
    df = dfs[0]

    # Normalisation simple des noms de colonnes
    rename_map = {}
    for col in df.columns:
        low = str(col).strip().lower()
        if low in ("jour", "date", "day"):
            rename_map[col] = "date"
        if low in ("horaire", "creneau", "créneau", "heures"):
            rename_map[col] = "horaire"
    if rename_map:
        df = df.rename(columns=rename_map)

    # ✅ pipeline : crée start/end/start_dt/end_dt proprement
    df = ensure_datetimes_pipeline(
        df,
        date_col="date",
        horaire_col="horaire",
        start_col="start",
        end_col="end",
        start_dt_col="start_dt",
        end_dt_col="end_dt",
        dayfirst=True,
    )
    return df

async def analyze_planning_from_url(url: str) -> Dict[str, Any]:
    html = await _fetch_text(url)
    df = _parse_html_to_dataframe(html)

    findings = []
    total_rows = int(df.shape[0])

    if total_rows == 0:
        raise PlanningAnalysisError("Le tableau des plannings est vide.")

    null_start = int(df["start_dt"].isna().sum()) if "start_dt" in df.columns else total_rows
    if null_start > 0:
        findings.append({
            "type": "warning",
            "message": f"{null_start} lignes sans heure de début exploitable."
        })

    return {
        "status": "ok",
        "source": url,
        "meta": {"rows": total_rows},
        "findings": findings,
        "preview": df.head(10).to_dict(orient="records"),
    }
