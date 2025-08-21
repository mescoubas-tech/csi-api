# app/plannings/ingest.py
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import pdfplumber  # extraction de tableaux PDF "natifs"
except Exception:  # pragma: no cover
    pdfplumber = None

from fastapi import UploadFile


def _safe_lower(s: Optional[str]) -> str:
    """Lowercase tolérant au None."""
    return (s or "").lower()


def _detect_format(upload: UploadFile) -> str:
    """
    Devine le type de fichier: csv/xlsx/pdf/unknown
    - Ne jette plus d'exception si filename ou content_type est None
    """
    name = upload.filename or ""  # peut être None selon le navigateur
    ext = _safe_lower(Path(name).suffix) if name else ""
    ctype = _safe_lower(getattr(upload, "content_type", None))

    # Priorité à l'extension
    if ext in (".csv",):
        return "csv"
    if ext in (".xlsx", ".xls"):
        return "xlsx"
    if ext in (".pdf",):
        return "pdf"

    # Sinon on tente le content-type
    if "csv" in ctype:
        return "csv"
    if "excel" in ctype or "spreadsheetml" in ctype:
        return "xlsx"
    if "pdf" in ctype:
        return "pdf"

    return "unknown"


async def load_schedule(upload: UploadFile) -> pd.DataFrame:
    """
    Charge un planning en DataFrame depuis CSV/XLSX/PDF natif.
    - Tolère content_type/filename manquants.
    - Donne des messages d'erreur explicites.
    """
    kind = _detect_format(upload)

    # Lecture des octets (UploadFile est un file-like asynchrone)
    data = await upload.read()
    bio = BytesIO(data)

    if kind == "csv":
        # sep=None + engine='python' pour détecter ; ; , \t automatiquement
        try:
            return pd.read_csv(bio, sep=None, engine="python")
        except Exception as e:
            raise ValueError(f"Lecture CSV impossible : {e}") from e

    if kind == "xlsx":
        try:
            return pd.read_excel(bio)
        except Exception as e:
            raise ValueError(f"Lecture Excel impossible : {e}") from e

    if kind == "pdf":
        if pdfplumber is None:
            raise ValueError(
                "Lecture PDF indisponible (dépendance pdfplumber manquante sur l’hébergement)."
            )
        try:
            rows = []
            with pdfplumber.open(bio) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables() or []
                    for t in tables:
                        for row in t:
                            rows.append(row)

            if not rows:
                raise ValueError(
                    "Aucune table lisible trouvée dans le PDF (PDF probablement scanné). "
                    "Convertissez en CSV/XLSX ou utilisez un PDF 'natif'."
                )

            width = max(len(r) for r in rows)
            norm = [(r + [""] * (width - len(r))) for r in rows]
            df = pd.DataFrame(norm)
            # Option : essayer de détecter une ligne d'en-têtes plausible
            # Ici on ne force rien pour rester générique.
            return df

        except Exception as e:
            raise ValueError(f"Lecture PDF impossible : {e}") from e

    # Si on arrive ici : format pas géré
    raise ValueError(
        f"Format non supporté. Nom='{upload.filename}', Content-Type='{getattr(upload, 'content_type', None)}'. "
        "Formats acceptés : CSV, XLSX ou PDF 'natif' (non scanné)."
    )
