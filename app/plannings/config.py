from __future__ import annotations
from datetime import time
from pydantic_settings import BaseSettings
from pydantic import BaseModel, Field


class RuleSettings(BaseModel):
    # Seuils légaux courants (France) — ajuste si besoin
    max_daily_hours: float = Field(10.0, description="Durée max/jour (heures)")
    max_weekly_hours: float = Field(48.0, description="Durée max/semaine (heures)")
    max_avg_week_hours_12w: float = Field(44.0, description="Moyenne 12 semaines glissantes")
    min_daily_rest_hours: float = Field(11.0, description="Repos quotidien minimum")
    min_weekly_rest_hours: float = Field(35.0, description="Repos hebdomadaire minimum")
    max_consecutive_days: int = Field(6, description="Jours consécutifs max")
    min_break_after_6h_min: float = Field(0.5, description="Pause min (h) si poste ≥ 6h")
    # Paramètres activité
    night_start: time = time(21, 0)
    night_end: time = time(6, 0)
    allow_sunday: bool = True  # à adapter selon convention/accord

    # Formats
    date_formats: list[str] = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    time_separators: tuple[str, ...] = (":", "h")


class Settings(BaseSettings):
    RULES: RuleSettings = RuleSettings()


SETTINGS = Settings()

from __future__ import annotations

import os
from datetime import time
from typing import
