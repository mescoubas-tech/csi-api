# app/core/config.py
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # chemins par défaut
    RULES_PATH: str = "data/rules.yaml"
    LEARNING_DB: str = "data/learning_db.json"
    ENV: str = "production"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    """Retourne les paramètres de config (cachés)."""
    s = Settings()

    # Normalise les chemins en string
    s.RULES_PATH = str(Path(s.RULES_PATH))
    s.LEARNING_DB = str(Path(s.LEARNING_DB))

    # Crée le dossier data si besoin (utile sur Render)
    Path(s.LEARNING_DB).parent.mkdir(parents=True, exist_ok=True)

    return s
