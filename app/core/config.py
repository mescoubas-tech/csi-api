class Settings(BaseSettings):
    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    RULES_PATH: str = str(PROJECT_ROOT / "data" / "rules.yml")
    LEARNING_DB: str = str(PROJECT_ROOT / "data")
    UPLOADS_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    MAX_UPLOAD_MB: int = 25

    # ⬇️ Seuils planning (modifiables via variables d’env Render)
    MAX_HOURS_PER_DAY: float = 10.0
    MAX_HOURS_PER_WEEK: float = 48.0
    AVG_HOURS_PER_12W: float = 44.0
    MIN_DAILY_REST_HOURS: float = 11.0
    MIN_WEEKLY_REST_HOURS: float = 35.0
    MAX_CONSECUTIVE_DAYS: int = 6
