import os
from pydantic import BaseModel
from datetime import time
from typing import Optional


class Settings(BaseModel):
    # Paramètres métier : tu peux les adapter selon les règles CNAPS
    MIN_REPOS_JOURNALIER_HEURES: int = int(os.getenv("MIN_REPOS_JOURNALIER_HEURES", 11))
    MAX_HEURES_TRAVAIL_JOUR: int = int(os.getenv("MAX_HEURES_TRAVAIL_JOUR", 10))
    MAX_HEURES_TRAVAIL_SEMAINE: int = int(os.getenv("MAX_HEURES_TRAVAIL_SEMAINE", 48))
    MAX_HEURES_TRAVAIL_MOYENNE_12_SEMAINES: int = int(os.getenv("MAX_HEURES_TRAVAIL_MOYENNE_12_SEMAINES", 44))

    DEBUT_JOURNEE: time = time.fromisoformat(os.getenv("DEBUT_JOURNEE", "06:00"))
    FIN_JOURNEE: time = time.fromisoformat(os.getenv("FIN_JOURNEE", "21:00"))

    # Optionnel : chemins ou paramètres techniques
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "/tmp/uploads")


# Instance globale
SETTINGS = Settings()
