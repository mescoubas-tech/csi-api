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


def
