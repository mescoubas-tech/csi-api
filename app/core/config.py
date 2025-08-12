from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]  # .../src
    RULES_PATH: str = str(PROJECT_ROOT / "data" / "rules.yml")
    LEARNING_DB: str = str(PROJECT_ROOT / "data")  # par défaut: un dossier

def get_settings() -> Settings:
    return Settings()
