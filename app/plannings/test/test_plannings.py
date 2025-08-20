import pandas as pd
from app.plannings.ingest import load_schedule
from app.plannings.analysis import analyze

def test_planning_module_runs():
    csv = b"agent_id,date,start,end,pause_min\nT1,2025-07-01,08:00,18:00,30\n"
    df = load_schedule(csv, "x.csv")
    result = analyze(df)
    assert result.summary.agents == 1
    assert result.summary.days == 1
    assert result.summary.total_hours_effective > 0
