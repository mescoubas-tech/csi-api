from __future__ import annotations

from io import BytesIO
import re
from typing import Iterable

import pandas as pd
import pdfplumber
from fastapi import UploadFile, HTTPException

from .config import SETTINGS


# Colonnes attendues après normalisation
NORMALIZED_COLS = [
    "employee_id", "employee_name",
    "date", "start", "end",
    "site", "role"
]


def _is_pdf(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def _is_csv(filename: str) -> bool:
    return filename.lower().endswith(".csv")


def _is_excel(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xls"))


def _parse_time(txt: str | float | int | None) -> pd.Timestamp | None:
    """Convertit '08:30', '8h30', 8.5, etc. vers Timestamp (au 1900-01-01)."""
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None
    s = str(txt).strip()
    if not s:
        return None
    s = s.replace("H", "h")
    # 8h or 8h30 -> 8:00 / 8:30
    s = re.sub(r"^(\d{1,2})h$", r"\1:00", s)
    s = re.sub(r"^(\d{1,2})h(\d{2})$", r"\1:\2", s)
    # 0830 -> 08:30
    if re.fullmatch(r"\d{3,4}", s):
        s = f"{s[:-2]}:{s[-2:]}"
    try:
        t = pd.to_datetime(s).time()
        return pd.Timestamp.combine(pd.Timestamp(1900, 1, 1), t)
    except Exception:
        # Excel times (0.3541666…)
        try:
            v = float(s)
            # 1 jour = 24h -> v * 24 heures
            minutes = round(v * 24 * 60)
            hh, mm = divmod(minutes, 60)
            hh %= 24
            return pd.Timestamp(1900, 1, 1, hh, mm)
        except Exception:
            return None


def _parse_date(txt: str) -> pd.Timestamp | None:
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None
    s = str(txt).strip()
    for fmt in SETTINGS.RULES.date_formats:
        try:
            return pd.to_datetime(s, format=fmt, dayfirst=True)
        except Exception:
            pass
    # fallback auto
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce")
    except Exception:
        return None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Essaie de retrouver les colonnes utiles malgré des intitulés variables."""
    colmap = {c.lower().strip(): c for c in df.columns}
    def find(*cands: Iterable[str]) -> str | None:
        for cand in cands:
            lc = cand.lower()
            if lc in colmap: return colmap[lc]
            # fuzzy
            for k in colmap:
                if lc in k:
                    return colmap[k]
        return None

    cid   = find("matricule", "id", "employee_id", "numéro", "code")
    cnom  = find("nom", "salarié", "agent", "employee", "collaborateur")
    cdate = find("date", "jour", "day")
    cstart= find("debut", "début", "start", "heure début", "heure_debut", "h début")
    cend  = find("fin", "end", "heure fin", "heure_fin", "h fin")
    csite = find("site", "lieu", "client", "poste")
    crole = find("role", "rôle", "fonction", "position")

    take = {}
    take["employee_id"] = df.get(cid) if cid else None
    take["employee_name"] = df.get(cnom) if cnom else None
    take["date"] = df.get(cdate) if cdate else None
    take["start"] = df.get(cstart) if cstart else None
    take["end"] = df.get(cend) if cend else None
    take["site"] = df.get(csite) if csite else None
    take["role"] = df.get(crole) if crole else None

    out = pd.DataFrame(take)
    # fallback : si pas d’ID, utilise le nom
    if "employee_id" in out and out["employee_id"].isna().all():
        out["employee_id"] = out["employee_name"]
    return out


def _read_csv_auto(content: bytes) -> pd.DataFrame:
    # essaie ; , \t
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(BytesIO(content), sep=sep, engine="python")
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    # fallback
    return pd.read_csv(BytesIO(content), engine="python")


def _read_pdf_tables(content: bytes) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for tbl in tables:
                # première ligne = en-têtes ? si plausible on la garde
                if tbl and len(tbl) > 1:
                    header = tbl[0]
                    for line in tbl[1:]:
                        rows.append(dict(zip(header, line)))
    if not rows:
        raise HTTPException(400, "Le PDF ne contient pas de tableau exploitable (pas d’OCR).")
    return pd.DataFrame(rows)


def load_schedule(file: UploadFile) -> pd.DataFrame:
    """Lit un planning multi-formats et renvoie un DataFrame normalisé."""
    content = file.file.read()
    if _is_csv(file.filename):
        df = _read_csv_auto(content)
    elif _is_excel(file.filename):
        df = pd.read_excel(BytesIO(content))
    elif _is_pdf(file.filename):
        df = _read_pdf_tables(content)
    else:
        raise HTTPException(400, "Format non supporté (utiliser .csv, .xlsx, .pdf numérique).")

    if df.empty:
        raise HTTPException(400, "Fichier vide ou illisible.")

    df = _normalize_columns(df)

    # Nettoyages/parsing
    df["date"]  = df["date"].apply(_parse_date)
    df["start"] = df["start"].apply(_parse_time)
    df["end"]   = df["end"].apply(_parse_time)

    # drop lignes incomplètes
    df = df.dropna(subset=["employee_id", "date", "start", "end"]).copy()

    # calcul durée (en heures, gère post-minuit)
    def _dur(row):
        s, e = row["start"].time(), row["end"].time()
        s_ts, e_ts = row["start"], row["end"]
        # si end < start, on considère dépassement après minuit
        delta = (e_ts - s_ts).total_seconds()
        if delta < 0:
            delta += 24 * 3600
        return round(delta / 3600.0, 2)

    df["hours"] = df.apply(_dur, axis=1)

    # clé jour
    df["day"] = df["date"].dt.date

    return df[NORMALIZED_COLS + ["hours", "day"]]
