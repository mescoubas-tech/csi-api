from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    RULES_PATH: str = str(PROJECT_ROOT / "data" / "rules.yml")
    LEARNING_DB: str = str(PROJECT_ROOT / "data")
    UPLOADS_DIR: str = str(PROJECT_ROOT / "data" / "uploads")  # <— dossier uploads
    MAX_UPLOAD_MB: int = 25  # limite par fichier

def get_settings() -> Settings:
    return Settings()
