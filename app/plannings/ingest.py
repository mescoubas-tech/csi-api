# app/plannings/ingest.py
import io
import re
from typing import List
import pandas as pd
import pdfplumber

REQUIRED_COLS = ["agent_id", "date", "start", "end"]

COLUMN_ALIASES = {
    "agent": "agent_id", "matricule": "agent_id", "id": "agent_id",
    "collaborateur": "agent_id", "intervenant": "agent_id",
    "jour": "date", "date_jour": "date",
    "debut": "start", "début": "start", "heure_debut": "start", "heure début": "start",
    "fin": "end", "heure_fin": "end", "heure fin": "end",
    "pause": "pause_min", "pause (min)": "pause_min",
    "nom": "nom", "prénom": "prenom", "prenom": "prenom",
    "site": "site", "employeur": "employer", "entreprise": "employer",
    "derog12h": "has_derogation_daily_12h", "derog_12h": "has_derogation_daily_12h",
    "mineur": "is_minor", "nuit": "is_night_worker",
}

OPTIONAL_COLS = [
    "pause_min", "nom", "prenom", "site", "employer",
    "has_derogation_daily_12h", "is_minor", "is_night_worker"
]

TIME_PAT = re.compile(r"^\s*(\d{1,2})[:hH\.](\d{2})\s*$")

def _norm_colname(c: str) -> str:
    c = (c or "").strip().lower()
    c = c.replace("\n", " ").replace("\r", " ")
    c = re.sub(r"\s+", " ", c)
    return COLUMN_ALIASES.get(c, c)

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm_colname(str(c)) for c in df.columns]

    def fix_time(v):
        if pd.isna(v): return v
        s = str(v).strip()
        m = TIME_PAT.match(s)
        if m:
            hh = int(m.group(1)); mm = int(m.group(2))
            return f"{hh:02d}:{mm:02d}"
        if s.isdigit():
            try:
                hh = int(s)
                if 0 <= hh <= 24:
                    return f"{hh:02d}:00"
            except: pass
        return s

    for col in ["start", "end"]:
        if col in df.columns:
            df[col] = df[col].map(fix_time)

    if "pause_min" in df.columns:
        def to_min(v):
            if pd.isna(v): return 0
            s = str(v).strip()
            m = TIME_PAT.match(s)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
            if s.isdigit():
                return int(s)
            return 0
        df["pause_min"] = df["pause_min"].map(to_min)

    if "agent_id" not in df.columns:
        if "nom" in df.columns or "prenom" in df.columns:
            df["agent_id"] = (
                df.get("nom", "").astype(str).str.strip() + "_" +
                df.get("prenom", "").astype(str).str.strip()
            ).str.strip("_")
        else:
            df["agent_id"] = df.index.astype(str)

    df["pause_min"] = df.get("pause_min", 0).fillna(0).astype(int)
    for b in ["has_derogation_daily_12h", "is_minor", "is_night_worker"]:
        if b in df.columns:
            df[b] = (
                df[b].astype(str).str.strip().str.lower()
                .isin(["1", "true", "vrai", "yes", "oui"])
            )

    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = None

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes minimales manquantes: {missing}. Colonnes trouvées: {list(df.columns)}")

    return df[[*REQUIRED_COLS, *OPTIONAL_COLS]]

def _read_csv_or_excel(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError("Unsupported file format. Use CSV or Excel.")
    return _normalize_columns(df)

from typing import List
def _merge_pdf_tables(tables: List[pd.DataFrame]) -> pd.DataFrame:
    dfs = []
    for raw in tables:
        if raw is None or raw.empty:
            continue
        df = raw.copy()
        try:
            df.columns = [str(c).strip() for c in df.iloc[0]]
            df = df.iloc[1:].reset_index(drop=True)
        except Exception:
            pass
        df = df.dropna(axis=1, how="all").dropna(how="all")
        if not df.empty:
            dfs.append(df)
    if not dfs:
        raise ValueError("PDF lu mais tableaux vides. Vérifier la structure du document.")
    merged = pd.concat(dfs, ignore_index=True)
    return _normalize_columns(merged)

def _read_pdf_tables(file_bytes: bytes) -> pd.DataFrame:
    """Extraction de tableaux sur PDF numériques (pas d’OCR)."""
    tables: List[pd.DataFrame] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                page_tables = page.extract_tables() or []
                for t in page_tables:
                    if t:
                        tables.append(pd.DataFrame(t))
                if not page_tables:
                    t = page.extract_table()
                    if t:
                        tables.append(pd.DataFrame(t))
            except Exception:
                continue
    if not tables:
        raise ValueError("Aucun tableau détecté dans le PDF (probablement un scan).")
    return _merge_pdf_tables(tables)

def load_schedule(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls"):
        return _read_csv_or_excel(file_bytes, filename)
    if name.endswith(".pdf"):
        return _read_pdf_tables(file_bytes)
    raise ValueError("Unsupported file format. Use CSV, Excel, or PDF.")
