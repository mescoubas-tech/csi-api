# app/plannings/ingest.py
import io
import re
from typing import List
import pandas as pd

# PDF “numériques”
import pdfplumber

# OCR pour PDF scannés
import fitz  # PyMuPDF (rendu images)
from PIL import Image
import pytesseract


REQUIRED_COLS = ["agent_id", "date", "start", "end"]

# alias courants -> nom canonique
COLUMN_ALIASES = {
    # identifiants
    "agent": "agent_id", "matricule": "agent_id", "id": "agent_id",
    "collaborateur": "agent_id", "intervenant": "agent_id",
    # date
    "jour": "date", "date_jour": "date",
    # heures
    "debut": "start", "début": "start", "heure_debut": "start", "heure début": "start",
    "fin": "end", "heure_fin": "end", "heure fin": "end",
    # pause
    "pause": "pause_min", "pause (min)": "pause_min",
    # autres (conservés si présents)
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

    # heures -> HH:MM (ex: '8h', '08h00', '8:30', '8.30', '8' => '08:00')
    def fix_time(v):
        if pd.isna(v):
            return v
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
            except:
                pass
        return s

    for col in ["start", "end"]:
        if col in df.columns:
            df[col] = df[col].map(fix_time)

    # pause -> minutes (ex: '30', '0:30' -> 30)
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

    # si pas d'agent_id mais nom/prenom -> construit un id
    if "agent_id" not in df.columns:
        if "nom" in df.columns or "prenom" in df.columns:
            df["agent_id"] = (
                df.get("nom", "").astype(str).str.strip() + "_" +
                df.get("prenom", "").astype(str).str.strip()
            ).str.strip("_")
        else:
            df["agent_id"] = df.index.astype(str)

    # types
    df["pause_min"] = df.get("pause_min", 0).fillna(0).astype(int)
    for b in ["has_derogation_daily_12h", "is_minor", "is_night_worker"]:
        if b in df.columns:
            df[b] = (
                df[b].astype(str).str.strip().str.lower()
                .isin(["1", "true", "vrai", "yes", "oui"])
            )

    # colonnes manquantes -> None
    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = None

    # vérifie colonnes minimales
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


def _merge_pdf_tables(tables: List[pd.DataFrame]) -> pd.DataFrame:
    dfs = []
    for raw in tables:
        if raw is None or raw.empty:
            continue
        df = raw.copy()

        # essaie d'utiliser la première ligne comme header
        try:
            df.columns = [str(c).strip() for c in df.iloc[0]]
            df = df.iloc[1:].reset_index(drop=True)
        except Exception:
            # si déjà avec header correct, on laisse
            pass

        df = df.dropna(axis=1, how="all").dropna(how="all")
        if not df.empty:
            dfs.append(df)

    if not dfs:
        raise ValueError("PDF lu mais tableaux vides. Vérifier la structure du document.")

    merged = pd.concat(dfs, ignore_index=True)
    return _normalize_columns(merged)


def _read_pdf_tables(file_bytes: bytes) -> pd.DataFrame:
    """Essaye d’extraire des tableaux 'numériques' avec pdfplumber."""
    tables: List[pd.DataFrame] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                # essaie extract_tables (multi-table)
                page_tables = page.extract_tables() or []
                for t in page_tables:
                    if t:
                        tables.append(pd.DataFrame(t))
                # fallback single table
                if not page_tables:
                    t = page.extract_table()
                    if t:
                        tables.append(pd.DataFrame(t))
            except Exception:
                continue

    if not tables:
        raise ValueError("Aucun tableau détecté dans le PDF.")
    return _merge_pdf_tables(tables)


def _read_pdf_with_ocr(file_bytes: bytes, lang: str = "fra+eng") -> pd.DataFrame:
    """OCR pour PDF scannés : rend chaque page en image, OCR via Tesseract, reconstruit un tableau naïf."""
    # Rendre les pages en images
    images: List[Image.Image] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        # résolution suffisante pour OCR (≈ 200-300 DPI)
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    # OCR ligne par ligne (on récupère des lignes pour reconstituer un tableau grossier)
    lines_all_pages: List[List[str]] = []
    for img in images:
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DATAFRAME)
        if data is None or data.empty:
            continue
        # garde les mots valides
        data = data.dropna(subset=["text"])
        if data.empty:
            continue

        # groupement par ligne (line_num)
        page_lines = []
        for _, line_df in data.groupby("line_num"):
            # concatène les mots avec un espace
            text_line = " ".join([str(t) for t in line_df["text"].tolist() if str(t).strip()])
            text_line = re.sub(r"\s+", " ", text_line).strip()
            if text_line:
                page_lines.append(text_line)
        if page_lines:
            lines_all_pages.append(page_lines)

    # Heuristique simple : splitter par 2+ espaces pour fabriquer des colonnes
    rows = []
    for page_lines in lines_all_pages:
        for l in page_lines:
            cols = re.split(r"\s{2,}", l)
            rows.append(cols)

    if not rows:
        raise ValueError("OCR terminé mais aucun texte exploitable. Vérifier la qualité du scan.")

    # fabrique DataFrame en alignant sur la largeur max
    max_len = max(len(r) for r in rows)
    norm_rows = [r + [""] * (max_len - len(r)) for r in rows]
    df = pd.DataFrame(norm_rows)

    # première ligne => header
    df.columns = [str(c).strip() for c in df.iloc[0]]
    df = df.iloc[1:].reset_index(drop=True)

    return _normalize_columns(df)


def load_schedule(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()

    # CSV / Excel directs
    if name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls"):
        return _read_csv_or_excel(file_bytes, filename)

    # PDF : d'abord tables "numériques", sinon OCR
    if name.endswith(".pdf"):
        try:
            return _read_pdf_tables(file_bytes)
        except Exception:
            # fallback OCR
            return _read_pdf_with_ocr(file_bytes, lang="fra+eng")

    raise ValueError("Unsupported file format. Use CSV, Excel, or PDF.")
