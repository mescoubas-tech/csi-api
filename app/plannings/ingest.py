import pytesseract
from PIL import Image
import pdfplumber

def extract_text_from_pdf(file_path: str) -> str:
    """Extrait du texte brut d’un PDF via pdfplumber ou OCR si nécessaire"""
    text = ""

    # Essayer lecture directe
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    # Si aucun texte détecté, passer par OCR
    if not text.strip():
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                img = page.to_image(resolution=300).original
                text += pytesseract.image_to_string(img, lang="fra")

    return text

# ↓ NEW: lecture PDF
import pdfplumber

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
    "pause": "pause_min", "pause_min": "pause_min", "pause (min)": "pause_min",
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
DATE_PATS = [
    r"^\s*(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})\s*$",  # JJ/MM/AAAA
    r"^\s*(\d{4})[\/\-\.](\d{2})[\/\-\.](\d{2})\s*$",  # AAAA-MM-JJ
]

def _norm_colname(c: str) -> str:
    c = (c or "").strip().lower()
    c = c.replace("\n", " ").replace("\r", " ")
    c = re.sub(r"\s+", " ", c)
    return COLUMN_ALIASES.get(c, c)

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm_colname(str(c)) for c in df.columns]

    # convert “Heures” typiques en HH:MM (ex: '8h', '08h00', '8:30', '8.30')
    def fix_time(v):
        if pd.isna(v): return v
        s = str(v).strip()
        m = TIME_PAT.match(s)
        if m:
            hh = int(m.group(1)); mm = int(m.group(2))
            return f"{hh:02d}:{mm:02d}"
        # formats '8' ou '08' => 08:00
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

    # un minimum d'auto-remplissage
    if "agent_id" not in df.columns:
        # parfois “nom prénom” uniquement : fabrique un id
        if "nom" in df.columns or "prenom" in df.columns:
            df["agent_id"] = (df.get("nom", "").astype(str).str.strip() + "_" +
                              df.get("prenom", "").astype(str).str.strip()).str.strip("_")
        else:
            # fallback : index
            df["agent_id"] = df.index.astype(str)

    # types
    df["pause_min"] = df.get("pause_min", 0).fillna(0).astype(int)
    for b in ["has_derogation_daily_12h", "is_minor", "is_night_worker"]:
        if b in df.columns:
            df[b] = df[b].astype(str).str.strip().str.lower().isin(["1", "true", "vrai", "yes", "oui"])

    # garde uniquement colonnes attendues
    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = None

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

def _read_pdf_tables(file_bytes: bytes) -> pd.DataFrame:
    """Extrait tous les tableaux d'un PDF numérique et tente d'en déduire les colonnes requises."""
    tables = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                t = page.extract_table()
                if not t:  # certains pdfs exposent plusieurs tables
                    for tb in page.extract_tables() or []:
                        if tb: tables.append(pd.DataFrame(tb))
                    continue
                tables.append(pd.DataFrame(t))
            except Exception:
                continue

    if not tables:
        raise ValueError("Aucun tableau exploitable trouvé dans le PDF (si c'est un scan image, il faut l'OCR).")

    # Nettoyage & fusion
    dfs = []
    for raw in tables:
        # traite la première ligne comme en-têtes si elle ressemble à des titres
        df = raw.copy()
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        # jette les colonnes vides totales
        df = df.dropna(axis=1, how="all")
        # jette les lignes vides
        df = df.dropna(how="all")
        if not df.empty:
            dfs.append(df)

    if not dfs:
        raise ValueError("PDF lu mais tableaux vides. Vérifier la structure du document.")

    merged = pd.concat(dfs, ignore_index=True)
    merged = _normalize_columns(merged)

    # Vérifie présence des colonnes minimales
    missing = [c for c in REQUIRED_COLS if c not in merged.columns]
    if missing:
        raise ValueError(f"Colonnes minimales introuvables dans le PDF: {missing}. "
                         f"Colonnes détectées: {list(merged.columns)}")
    return merged

def load_schedule(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls"):
        return _read_csv_or_excel(file_bytes, filename)
    if name.endswith(".pdf"):
        return _read_pdf_tables(file_bytes)
    raise ValueError("Unsupported file format. Use CSV, Excel, or PDF.")
    import io, re
import pandas as pd
import pdfplumber
from PIL import Image
import easyocr

# ... (garde tout le code précédent)

def _read_pdf_with_ocr(file_bytes: bytes) -> pd.DataFrame:
    """OCR sur PDF scanné : extrait texte brut, tente de reconstruire un tableau simple."""
    reader = easyocr.Reader(["fr", "en"])
    texts = []

    import tempfile
    import fitz  # PyMuPDF pour convertir pages -> images
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        pdf = fitz.open(tmp.name)
        for page in pdf:
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            result = reader.readtext(np.array(img), detail=0)
            texts.append(" ".join(result))

    raw_text = "\n".join(texts)

    # Naïf : split par lignes et tabulations
    lines = [re.split(r"\s{2,}|\t", l.strip()) for l in raw_text.split("\n") if l.strip()]
    df = pd.DataFrame(lines)

    # traite la première ligne comme header
    if not df.empty:
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)

    return _normalize_columns(df)


def _read_pdf_tables(file_bytes: bytes) -> pd.DataFrame:
    """Extrait d'abord les tableaux numériques, sinon fallback OCR."""
    tables = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                t = page.extract_table()
                if not t:
                    continue
                tables.append(pd.DataFrame(t))
            except Exception:
                continue

    if not tables:
        # fallback OCR
        return _read_pdf_with_ocr(file_bytes)

    # Fusion et nettoyage comme avant
    dfs = []
    for raw in tables:
        df = raw.copy()
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.dropna(axis=1, how="all").dropna(how="all")
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return _read_pdf_with_ocr(file_bytes)

    merged = pd.concat(dfs, ignore_index=True)
    merged = _normalize_columns(merged)
    return merged
