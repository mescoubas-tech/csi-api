import io
import pandas as pd

REQUIRED_COLS = ["agent_id", "date", "start", "end"]
OPTIONAL_COLS = [
    "pause_min","nom","prenom","site","employer",
    "has_derogation_daily_12h","is_minor","is_night_worker"
]

def load_schedule(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError("Unsupported file format. Use CSV or Excel.")
    df.columns = [c.strip().lower() for c in df.columns]
    for col in REQUIRED_COLS:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    for col in OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = None
    df["pause_min"] = df["pause_min"].fillna(0).astype(int)
    for b in ["has_derogation_daily_12h","is_minor","is_night_worker"]:
        df[b] = df[b].fillna(False).astype(bool)
    for c in ["agent_id","nom","prenom","site","employer"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df[REQUIRED_COLS + OPTIONAL_COLS]
