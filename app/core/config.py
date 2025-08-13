# app/core/config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Variables d'env prefixées "CSI_" (ex: CSI_MAX_UPLOAD_MB)
    model_config = SettingsConfigDict(env_prefix="CSI_", case_sensitive=False)

    # Chemins par défaut
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    RULES_PATH: str = str(PROJECT_ROOT / "data" / "rules.yml")
    LEARNING_DB: str = str(PROJECT_ROOT / "data")
    UPLOADS_DIR: str = str(PROJECT_ROOT / "data" / "uploads")

    # Limites d'upload
    MAX_UPLOAD_MB: int = 25

    # Seuils droit du travail (adaptables via variables d'env)
    MAX_HOURS_PER_DAY: float = 10.0
    MAX_HOURS_PER_WEEK: float = 48.0
    AVG_HOURS_PER_12W: float = 44.0
    MIN_DAILY_REST_HOURS: float = 11.0
    MIN_WEEKLY_REST_HOURS: float = 35.0
    MAX_CONSECUTIVE_DAYS: int = 6

def get_settings() -> Settings:
    return Settings()
