# app/services/pdf_schedule_parser.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import re
import pdfplumber
from datetime import datetime

# Entêtes possibles dans les PDF
HEADER_ALIASES: Dict[str, str] = {
    "agent": "agent_id",
    "salarié": "agent_id",
    "collaborateur": "agent_id",
    "matricule": "agent_id",
    "id": "agent_id",

    "date": "date",
    "jour": "date",

    "début": "start_time",
    "debut": "start_time",
    "heure début": "start_time",
    "debut poste": "start_time",
    "start": "start_time",

    "fin": "end_time",
    "heure fin": "end_time",
    "fin poste": "end_time",
    "end": "end_time",

    "pause": "break_minutes",
    "pause (min)": "break_minutes",
    "break": "break_minutes",
}

TIME_RE = re.compile(r"^\s*(\d{1,2})[:hH\.](\d{2})\s*$")
DATE_PATTERNS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")

def _norm_header(cell: str) -> Optional[str]:
    if cell is None:
        return None
    key = re.sub(r"\s+", " ", str(cell)).strip().lower()
    key = key.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("’", "'")
    return HEADER_ALIASES.get(key)

def _parse_time(s: str) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip().lower().replace(" ", "")
    s = s.replace(".", ":").replace("h", ":")
    m = TIME_RE.match(s)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh <= 47 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return None

def _parse_date(s: str) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    # 01-08-2025
    s2 = s.replace(".", "/").replace("-", "/")
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(s2, fmt).date().isoformat()
        except Exception:
            pass
    return None

def _parse_break_minutes(s: str) -> int:
    if s is None or str(s).strip() == "":
        return 0
    txt = str(s).lower().replace("min", "").strip()
    txt = txt.replace(",", ".")
    m = re.search(r"(\d+)", txt)
    if m:
        return int(m.group(1))
    return 0

def extract_rows_from_pdf(path: Path) -> List[dict]:
    """Lit les tableaux d'un PDF et renvoie une liste de dict normalisés."""
    rows: List[dict] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_x_tolerance": 3,
                "intersection_y_tolerance": 3,
                "text_tolerance": 3,
            }) or []
            for tbl in tables:
                if not tbl or len(tbl) < 2:
                    continue
                header = tbl[0]
                mapping: Dict[int, str] = {}
                for idx, cell in enumerate(header):
                    norm = _norm_header(cell)
                    if norm:
                        mapping[idx] = norm
                if not mapping:
                    continue  # table non reconnue

                for r in tbl[1:]:
                    rec: Dict[str, Optional[str]] = {}
                    for i, v in enumerate(r):
                        key = mapping.get(i)
                        if not key:
                            continue
                        val = (v or "").strip() if isinstance(v, str) else v
                        rec[key] = val

                    agent = (rec.get("agent_id") or "").strip()
                    date = _parse_date(rec.get("date"))
                    st = _parse_time(rec.get("start_time"))
                    en = _parse_time(rec.get("end_time"))
                    br = _parse_break_minutes(rec.get("break_minutes"))

                    if agent and date and st and en is not None:
                        rows.append({
                            "agent_id": agent,
                            "date": date,
                            "start_time": st,
                            "end_time": en,
                            "break_minutes": br,
                        })
    return rows

def parse_pdf_schedules(paths: Iterable[Path]) -> List[dict]:
    out: List[dict] = []
    for p in paths:
        try:
            out.extend(extract_rows_from_pdf(Path(p)))
        except Exception:
            # On ignore les PDF illisibles; ils seront comptés ailleurs
            continue
    return out
