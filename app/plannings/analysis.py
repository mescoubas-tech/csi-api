import pandas as pd
from app.plannings.rules import build_daily, detect_alerts
from pydantic import BaseModel

class Summary(BaseModel):
    agents: int
    days: int
    total_hours_effective: float
    total_hours_night: float
    alerts_count: int

class AnalysisResult(BaseModel):
    summary: Summary
    alerts: list
    by_agent: dict

def analyze(df: pd.DataFrame) -> AnalysisResult:
    daily = build_daily(df)
    alerts = detect_alerts(daily)
    summary = Summary(
        agents=daily["agent_id"].nunique(),
        days=daily["work_day"].nunique(),
        total_hours_effective=float(daily["hours_effective"].sum()),
        total_hours_night=float(daily["hours_night"].sum()),
        alerts_count=len(alerts),
    )
    per_agent = daily.groupby("agent_id").agg(
        hours_effective=("hours_effective","sum"),
        hours_night=("hours_night","sum"),
        days=("work_day","nunique")
    ).reset_index()
    by_agent = {
        row["agent_id"]: {
            "hours_effective": float(row["hours_effective"]),
            "hours_night": float(row["hours_night"]),
            "days": int(row["days"]),
        } for _, row in per_agent.iterrows()
    }
    return AnalysisResult(summary=summary, alerts=alerts, by_agent=by_agent)
