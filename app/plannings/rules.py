from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta, time
from dateutil.parser import parse as dt_parse
from app.plannings.config import SETTINGS

def _to_dt(date_str: str, t_str: str) -> datetime:
    d = dt_parse(date_str).date()
    ts = dt_parse(t_str).time()
    return datetime.combine(d, ts)

def compute_effective_hours(row) -> float:
    start_dt = _to_dt(row["date"], row["start"])
    end_dt = _to_dt(row["date"], row["end"])
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    dur_h = (end_dt - start_dt).total_seconds() / 3600.0
    pause = float(row.get("pause_min", 0) or 0) / 60.0
    return max(dur_h - pause, 0.0)

def compute_night_hours(row) -> float:
    rs = SETTINGS.rules
    start_dt = _to_dt(row["date"], row["start"])
    end_dt = _to_dt(row["date"], row["end"])
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    ns, ne = rs.night_start_hour, rs.night_end_hour
    night1_start = datetime.combine(start_dt.date(), time(hour=ns))
    night1_end   = datetime.combine(start_dt.date(), time(23,59,59))
    night2_start = datetime.combine(start_dt.date()+timedelta(days=1), time(0,0,0))
    night2_end   = datetime.combine(start_dt.date()+timedelta(days=1), time(hour=ne))
    def ov(a1,a2,b1,b2):
        s=max(a1,b1); e=min(a2,b2); return max((e-s).total_seconds(),0)
    return (ov(start_dt,end_dt,night1_start,night1_end)+ov(start_dt,end_dt,night2_start,night2_end))/3600.0

def build_daily(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["hours_effective"] = d.apply(compute_effective_hours, axis=1)
    d["hours_night"] = d.apply(compute_night_hours, axis=1)
    d["work_day"] = pd.to_datetime(d["date"]).dt.date
    d["worked_flag"] = (d["hours_effective"] > 0).astype(int)
    return d

def build_weekly(agent_daily: pd.DataFrame) -> pd.DataFrame:
    wk = agent_daily.copy()
    wk["iso_year"] = pd.to_datetime(wk["work_day"]).dt.isocalendar().year
    wk["iso_week"] = pd.to_datetime(wk["work_day"]).dt.isocalendar().week
    return wk.groupby(["agent_id","iso_year","iso_week"], as_index=False).agg(
        hours_effective_week=("hours_effective","sum"),
        days_worked=("worked_flag","sum"),
    )

def build_12w_rolling(weekly: pd.DataFrame) -> pd.DataFrame:
    w = weekly.copy().sort_values(["agent_id","iso_year","iso_week"])
    w["yearweek"] = w["iso_year"]*100 + w["iso_week"]
    out=[]
    for agent, grp in w.groupby("agent_id"):
        g = grp.sort_values("yearweek")
        g["avg12w"] = g["hours_effective_week"].rolling(window=12, min_periods=1).mean()
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else w

def detect_alerts(daily: pd.DataFrame) -> List[Dict[str, Any]]:
    rs = SETTINGS.rules
    alerts: List[Dict[str, Any]] = []
    dsum = daily.groupby(["agent_id","work_day"], as_index=False).agg(
        hours=("hours_effective","sum"),
        has_derogation=("has_derogation_daily_12h","max")
    )
    for _, r in dsum.iterrows():
        limit = rs.max_daily_hours_with_derog if bool(r["has_derogation"]) else rs.max_daily_hours
        if r["hours"] > limit + 1e-6:
            alerts.append({"rule_id":"DAILY_MAX","agent_id":r["agent_id"],"date":r["work_day"].isoformat(),
                           "severity":"error","message":f"Heures quotidiennes {r['hours']:.2f} > {limit}",
                           "evidence":{"hours":float(r["hours"]),"limit":float(limit)}})
    weekly = build_weekly(daily)
    for _, r in weekly.iterrows():
        if r["hours_effective_week"] > rs.max_weekly_hours + 1e-6:
            alerts.append({"rule_id":"WEEKLY_48H","agent_id":r["agent_id"],
                           "date":f"ISO {int(r['iso_year'])}-W{int(r['iso_week'])}",
                           "severity":"error","message":f"Heures hebdo {r['hours_effective_week']:.2f} > {rs.max_weekly_hours}",
                           "evidence":{"hours_week":float(r["hours_effective_week"]), "limit":float(rs.max_weekly_hours)}})
    rolling = build_12w_rolling(weekly)
    for _, r in rolling.iterrows():
        if r["avg12w"] > rs.avg_weekly_hours_over_12_weeks + 1e-6:
            alerts.append({"rule_id":"AVG_12W_44H","agent_id":r["agent_id"],
                           "date":f"ISO {int(r['iso_year'])}-W{int(r['iso_week'])}",
                           "severity":"error","message":f"Moyenne 12 sem. {r['avg12w']:.2f} > {rs.avg_weekly_hours_over_12_weeks}",
                           "evidence":{"avg12w":float(r["avg12w"]), "limit":float(rs.avg_weekly_hours_over_12_weeks)}})
    for agent, grp in daily.sort_values(["agent_id","work_day","start"]).groupby("agent_id"):
        rows = grp.to_dict("records"); prev_end = None
        for row in rows:
            start_dt = dt_parse(f"{row['date']} {row['start']}")
            end_dt = dt_parse(f"{row['date']} {row['end']}")
            if end_dt <= start_dt: end_dt += pd.Timedelta(days=1)
            if prev_end is not None:
                rest_h = (start_dt - prev_end).total_seconds() / 3600.0
                min_rest = rs.min_daily_rest_hours if not bool(row.get("is_minor", False)) else max(rs.min_daily_rest_hours, rs.minor_min_daily_rest_hours)
                if rest_h < min_rest - 1e-6:
                    alerts.append({"rule_id":"DAILY_REST_11H","agent_id":agent,"date":row["date"],
                                   "severity":"error","message":f"Repos quotidien {rest_h:.2f} h < {min_rest} h",
                                   "evidence":{"rest_hours":float(rest_h), "limit":float(min_rest)}})
            prev_end = end_dt
    by_agent_date = daily.groupby(["agent_id","work_day"], as_index=False).agg(
        end_last=("end","last"), start_first=("start","first")
    ).sort_values(["agent_id","work_day"])
    for agent, grp in by_agent_date.groupby("agent_id"):
        grp = grp.sort_values("work_day"); prev_end_dt=None; had_35h=False
        for _, row in grp.iterrows():
            end_dt = dt_parse(f"{row['work_day']} {row['end_last']}")
            start_dt = dt_parse(f"{row['work_day']} {row['start_first']}")
            if end_dt <= start_dt: end_dt += pd.Timedelta(days=1)
            if prev_end_dt is not None:
                gap_h = (start_dt - prev_end_dt).total_seconds()/3600.0
                if gap_h >= rs.min_weekly_rest_hours - 1e-6: had_35h=True
            prev_end_dt = end_dt
        if not had_35h and len(grp) >= 6:
            alerts.append({"rule_id":"WEEKLY_REST_35H","agent_id":agent,"date":None,
                           "severity":"warning","message":"Repos hebdomadaire ≥ 35 h non trouvé","evidence":{}})
    for _, r in dsum.iterrows():
        if r["hours"] >= 6.0:
            pauses = daily[(daily["agent_id"]==r["agent_id"]) & (daily["work_day"]==r["work_day"])].get("pause_min",0)
            pause_total = float(pauses.sum()) if hasattr(pauses,"sum") else float(pauses or 0)
            if pause_total < rs.min_break_minutes_after_6h - 1e-6:
                alerts.append({"rule_id":"BREAK_20M","agent_id":r["agent_id"],"date":r["work_day"].isoformat(),
                               "severity":"warning","message":f"Pause {pause_total:.0f} min < {rs.min_break_minutes_after_6h} min (≥ 6 h)",
                               "evidence":{"pause_min":float(pause_total), "limit_min":float(rs.min_break_minutes_after_6h)}})
    minors = daily[daily.get("is_minor", False)==True] if "is_minor" in daily.columns else pd.DataFrame()
    if not minors.empty:
        for _, row in minors.iterrows():
            start_dt = dt_parse(f"{row['date']} {row['start']}")
            end_dt = dt_parse(f"{row['date']} {row['end']}")
            if end_dt <= start_dt: end_dt += pd.Timedelta(days=1)
            forbidden_start = start_dt.replace(hour=rs.minor_night_forbidden_start, minute=0, second=0, microsecond=0)
            forbidden_end   = (start_dt + pd.Timedelta(days=1)).replace(hour=rs.minor_night_forbidden_end, minute=0, second=0, microsecond=0)
            if (min(end_dt,forbidden_end) - max(start_dt,forbidden_start)).total_seconds() > 0:
                alerts.append({"rule_id":"MINOR_NIGHT_FORBIDDEN","agent_id":row["agent_id"],"date":row["date"],
                               "severity":"error","message":"Plage de nuit interdite pour mineur (22h–6h) détectée",
                               "evidence":{"start":row["start"],"end":row["end"]}})
    day_flags = daily.groupby(["agent_id","work_day"], as_index=False)["worked_flag"].max().sort_values(["agent_id","work_day"])
    for agent, grp in day_flags.groupby("agent_id"):
        days = grp["work_day"].tolist(); streak=0; last_day=None
        for d in days:
            if last_day is None or (pd.to_datetime(d)-pd.to_datetime(last_day)).days==1:
                streak += 1
            else:
                if streak >= rs.max_consecutive_work_days:
                    alerts.append({"rule_id":"TWO_DAYS_REST_AFTER_SIX","agent_id":agent,"date":None,
                                   "severity":"warning","message":f"{streak} jours consécutifs travaillés — vérifier 2 jours de repos",
                                   "evidence":{"streak_days":int(streak)}})
                streak = 1
            last_day = d
        if streak >= rs.max_consecutive_work_days:
            alerts.append({"rule_id":"TWO_DAYS_REST_AFTER_SIX","agent_id":agent,"date":None,
                           "severity":"warning","message":f"{streak} jours consécutifs travaillés — vérifier 2 jours de repos",
                           "evidence":{"streak_days":int(streak)}})
    return alerts
