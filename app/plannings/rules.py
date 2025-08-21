from __future__ import annotations
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import SETTINGS


@dataclass
class Violation:
    employee_id: str
    employee_name: str | None
    date: str
    code: str
    message: str
    details: dict[str, Any]


def analyze_schedule(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calcule les non-conformités clés :
    - durée journalière max
    - durée hebdomadaire max
    - repos quotidien (>= 11h) entre 2 postes
    - repos hebdomadaire (>= 35h)
    - jours consécutifs (> 6)
    - pause ≥ 30min si poste >= 6h (approx. en l’absence de colonnes de pause)
    """
    R = SETTINGS.RULES
    violations: list[dict[str, Any]] = []

    if df.empty:
        return {"summary": {}, "violations": []}

    # index utiles
    df = df.sort_values(["employee_id", "date", "start"]).copy()

    # Par jour & salarié : somme des heures
    daily = df.groupby(["employee_id", "employee_name", "day"], as_index=False)["hours"].sum()
    daily["week"] = pd.to_datetime(daily["day"]).dt.isocalendar().week
    daily["year"] = pd.to_datetime(daily["day"]).dt.isocalendar().year

    # 1) Durée journalière max
    mask = daily["hours"] > R.max_daily_hours
    for _, r in daily[mask].iterrows():
        violations.append(Violation(
            r.employee_id, r.employee_name, str(r.day),
            "MAX_DAILY", f"Durée journalière {r.hours}h > {R.max_daily_hours}h",
            {"hours": r.hours}
        ).__dict__)

    # 2) Durée hebdomadaire max
    weekly = daily.groupby(["employee_id", "employee_name", "year", "week"], as_index=False)["hours"].sum()
    mask = weekly["hours"] > R.max_weekly_hours
    for _, r in weekly[mask].iterrows():
        violations.append(Violation(
            r.employee_id, r.employee_name, f"S{int(r.week)}-{int(r.year)}",
            "MAX_WEEKLY", f"Durée hebdomadaire {r.hours}h > {R.max_weekly_hours}h",
            {"hours": r.hours}
        ).__dict__)

    # 3) Repos quotidien (>= 11h) entre deux vacations
    # On calcule l'écart entre la fin d'un service et le début du suivant (même salarié)
    df["start_dt"] = pd.to_datetime(df["date"].dt.date) + (df["start"] - pd.Timestamp("1900-01-01"))
    df["end_dt"]   = pd.to_datetime(df["date"].dt.date) + (df["end"]   - pd.Timestamp("1900-01-01"))
    # si fin < début => +1 jour
    mask_wrap = (df["end_dt"] < df["start_dt"])
    df.loc[mask_wrap, "end_dt"] = df.loc[mask_wrap, "end_dt"] + pd.Timedelta(days=1)

    df = df.sort_values(["employee_id", "start_dt"])
    df["prev_end"] = df.groupby("employee_id")["end_dt"].shift()
    df["rest_hours"] = (df["start_dt"] - df["prev_end"]).dt.total_seconds() / 3600.0
    mask = df["prev_end"].notna() & (df["rest_hours"] < R.min_daily_rest_hours)
    for _, r in df[mask].iterrows():
        violations.append(Violation(
            r.employee_id, r.employee_name, str(r.date.date()),
            "DAILY_REST", f"Repos quotidien {round(r.rest_hours,2)}h < {R.min_daily_rest_hours}h",
            {"rest_hours": round(r.rest_hours,2)}
        ).__dict__)

    # 4) Repos hebdomadaire (>= 35h)
    # on repère des séquences avec écart >= 35h sur la semaine ; si aucune -> violation
    # Approximation : on cherche, pour chaque semaine, s'il existe au moins une fenêtre de repos >= 35h
    weekly_rest_viol = []
    for (emp, yr, wk), grp in df.groupby(["employee_id", df["start_dt"].dt.isocalendar().year, df["start_dt"].dt.isocalendar().week]):
        grp = grp.sort_values("start_dt")
        # concatène toutes les fins & débuts pour trouver les repos
        ends = grp["end_dt"].tolist()
        starts = grp["start_dt"].tolist()
        ok = False
        for i in range(len(grp)-1):
            rest = (starts[i+1] - ends[i]).total_seconds()/3600.0
            if rest >= R.min_weekly_rest_hours:
                ok = True
                break
        if not ok and len(grp) > 0:
            weekly_rest_viol.append((emp, yr, wk))
    for emp, yr, wk in weekly_rest_viol:
        name = df[df["employee_id"] == emp]["employee_name"].dropna().head(1).tolist()
        violations.append(Violation(
            emp, name[0] if name else None, f"S{int(wk)}-{int(yr)}",
            "WEEKLY_REST", f"Repos hebdomadaire < {R.min_weekly_rest_hours}h",
            {}
        ).__dict__)

    # 5) Jours consécutifs > seuil
    # on repère des suites de jours travaillés sans trou
    def consecutive_days(days: list[pd.Timestamp]) -> int:
        if not days: return 0
        days = sorted(set(pd.to_datetime(days)))
        maxi, cur = 1, 1
        for i in range(1, len(days)):
            if (days[i] - days[i-1]).days == 1:
                cur += 1
                maxi = max(maxi, cur)
            else:
                cur = 1
        return maxi

    for (emp, name), grp in daily.groupby(["employee_id", "employee_name"]):
        maxi = consecutive_days(pd.to_datetime(grp["day"]).tolist())
        if maxi > R.max_consecutive_days:
            violations.append(Violation(
                emp, name, "-", "CONSEC_DAYS",
                f"{maxi} jours travaillés consécutifs > {R.max_consecutive_days}",
                {"consecutive_days": int(maxi)}
            ).__dict__)

    # 6) Pause ≥ 30 min si poste >= 6h (approx.)
    # Si une vacation journalière >= 6h et aucune info de pause, on lève un warning
    long_shifts = df[(df["hours"] >= 6.0)]
    for _, r in long_shifts.iterrows():
        violations.append(Violation(
            r.employee_id, r.employee_name, str(r.date.date()),
            "BREAK_6H", f"Vacation de {r.hours}h — vérifier pause ≥ {SETTINGS.RULES.min_break_after_6h_min*60:.0f} min",
            {"hours": r.hours}
        ).__dict__)

    # Résumé
    summary = {
        "employees": int(daily["employee_id"].nunique()),
        "days": int(daily["day"].nunique()),
        "total_hours": float(round(daily["hours"].sum(), 2)),
        "violations_count": len(violations),
        "by_code": pd.Series([v["code"] for v in violations]).value_counts().to_dict() if violations else {},
    }

    return {"summary": summary, "violations": violations}
