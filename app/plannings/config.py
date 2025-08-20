from pydantic import BaseModel, Field

class RuleSettings(BaseModel):
    max_daily_hours: float = Field(10.0)
    max_daily_hours_with_derog: float = Field(12.0)
    max_weekly_hours: float = Field(48.0)
    avg_weekly_hours_over_12_weeks: float = Field(44.0)
    min_daily_rest_hours: float = Field(11.0)
    min_weekly_rest_hours: float = Field(35.0)
    min_break_minutes_after_6h: int = Field(20)
    night_start_hour: int = Field(21)
    night_end_hour: int = Field(6)
    max_consecutive_work_days: int = Field(6)
    minor_min_daily_rest_hours: float = Field(12.0)
    minor_night_forbidden_start: int = Field(22)
    minor_night_forbidden_end: int = Field(6)
    night_rest_comp_percent: float = Field(1.0)

class Settings(BaseModel):
    rules: RuleSettings = RuleSettings()

SETTINGS = Settings()
