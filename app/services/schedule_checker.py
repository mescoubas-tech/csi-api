from __future__ import annotations
import csv
import math
from datetime import datetime, timedelta, date, time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..core.config import get_settings
from ..models.schemas import SchedulesCheckResult, ScheduleStats, ScheduleViolation

# -------- Parsing fichiers --------

_COL_MAP = {
    "agent": "agent_id", "id": "agent_id", "matricule": "agent_id", "agent_id": "agent_id",
    "date": "date",
    "start": "start_time", "debut": "start_time", "heure_debut": "start_time", "debut_poste": "start_time",
    "end": "end_time", "fin": "end_time", "heure_fin": "end_time", "fin_poste": "end_time",
    "break": "break_minutes", "pause": "break_minutes", "pause_min": "break_minutes", "break_minutes": "break_minutes"
}

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_")

def _guess_map(headers: List[str]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for h in headers:
        k = _COL_MAP.get(_norm(h))
        if k: m[k] = h
    # champs indispensables
    for req in ("agent_id", "date", "start_time", "end_time"):
        if req not in m: raise ValueError(f"Colonne manquante: {req} (en-têtes: {headers})")
    return m

def _parse_date(s: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try: return datetime.strptime(s.strip(), fmt).date()
        except: pass
    raise ValueError(f"Date invalide: {s!r}")

def _parse_time(s: str) -> time:
    for fmt in ("%H:%M", "%H:%M:%S"):
        try: return datetime.strptime(s.strip(), fmt).time()
        except: pass
    raise ValueError(f"Heure invalide: {s!r}")

def _read_csv(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(4096); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = list(reader)
    return rows

def _read_xlsx(path: Path) -> List[dict]:
    try:
        import openpyxl  # type: ignore
    except Exception:
        raise RuntimeError("openpyxl requis pour lire les XLSX (ajoute-le à requirements.txt).")
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    headers = [str((c.value or "")).strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]
    rows: List[dict] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        row = {}
        for i, h in enumerate(headers):
            row[h] = "" if i >= len(r) or r[i] is None else str(r[i])
        rows.append(row)
    return rows

def read_schedules(files: Iterable[Path]) -> List[dict]:
    """Retourne une liste de shifts normalisés : {agent_id,date,start_time,end_time,break_minutes}"""
    shifts: List[dict] = []
    for p in files:
        p = Path(p)
        if not p.exists(): continue
        rows = _read_xlsx(p) if p.suffix.lower() in (".xlsx", ".xlsm") else _read_csv(p)
        if not rows: continue
        m = _guess_map(list(rows[0].keys()))
        for r in rows:
            agent = str(r[m["agent_id"]]).strip()
            d = _parse_date(str(r[m["date"]]))
            t1 = _parse_time(str(r[m["start_time"]]))
            t2 = _parse_time(str(r[m["end_time"]]))
            br = 0
            if "break_minutes" in m:
                try: br = int(float(str(r[m["break_minutes"]]).replace(",", ".") or "0"))
                except: br = 0
            start_dt = datetime.combine(d, t1)
            end_dt = datetime.combine(d, t2)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)  # nuit
            duration = (end_dt - start_dt).total_seconds()/3600.0 - br/60.0
            if duration < 0: duration = 0.0
            shifts.append({
                "agent_id": agent or "INCONNU",
                "date": d,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "hours": duration
            })
    # ordonner par agent puis début
    shifts.sort(key=lambda x: (x["agent_id"], x["start_dt"]))
    return shifts

# -------- Contrôles --------

def iso_week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

def check_schedules(files: Iterable[Path]) -> SchedulesCheckResult:
    s = get_settings()
    shifts = read_schedules(files)
    if not shifts:
        return SchedulesCheckResult(agents=[], stats=[], violations=[], extras={"note": "Aucun shift lu."})

    agents = sorted({x["agent_id"] for x in shifts})
    # agrégats
    by_agent: Dict[str, List[dict]] = {a: [] for a in agents}
    for sh in shifts: by_agent[sh["agent_id"]].append(sh)

    violations: List[ScheduleViolation] = []
    stats: List[ScheduleStats] = []

    # périodes
    period_start = min(x["start_dt"].date() for x in shifts)
    period_end = max(x["end_dt"].date() for x in shifts)

    for a in agents:
        A = by_agent[a]
        # stats totales
        total_hours = round(sum(x["hours"] for x in A), 2)
        days_worked = len({x["start_dt"].date() for x in A})
        # weekly totals
        weekly: Dict[str, float] = {}
        for x in A:
            k = iso_week_key(x["start_dt"].date())
            weekly[k] = weekly.get(k, 0.0) + x["hours"]

        # 1) Max journalier
        per_day: Dict[date, float] = {}
        for x in A:
            d = x["start_dt"].date()
            per_day[d] = per_day.get(d, 0.0) + x["hours"]
        for d, h in per_day.items():
            if h > s.MAX_HOURS_PER_DAY + 1e-6:
                violations.append(ScheduleViolation(
                    agent_id=a, type="DAILY_MAX", date=d,
                    details=f"{h:.2f} h travaillées (max {s.MAX_HOURS_PER_DAY} h)",
                    value=round(h,2), threshold=s.MAX_HOURS_PER_DAY
                ))

        # 2) Max hebdo 48h
        for wk, h in weekly.items():
            if h > s.MAX_HOURS_PER_WEEK + 1e-6:
                violations.append(ScheduleViolation(
                    agent_id=a, type="WEEKLY_MAX", week=wk,
                    details=f"{h:.2f} h sur la semaine {wk} (max {s.MAX_HOURS_PER_WEEK} h)",
                    value=round(h,2), threshold=s.MAX_HOURS_PER_WEEK
                ))

        # 3) Moyenne 12 semaines <= 44h
        weeks_sorted = sorted(weekly.keys())
        hours_list = [weekly[w] for w in sorted(weekly.keys())]
        # fenêtre glissante de 12 semaines
        for i in range(0, len(hours_list)):
            j = min(i+12, len(hours_list))
            if j - i == 12:
                avg = sum(hours_list[i:j]) / 12.0
                if avg > s.AVG_HOURS_PER_12W + 1e-6:
                    wkwin = f"{weeks_sorted[i]}..{weeks_sorted[j-1]}"
                    violations.append(ScheduleViolation(
                        agent_id=a, type="AVG_12W", week=wkwin,
                        details=f"Moyenne {avg:.2f} h / semaine sur 12 sem. (max {s.AVG_HOURS_PER_12W} h)",
                        value=round(avg,2), threshold=s.AVG_HOURS_PER_12W
                    ))

        # 4) Repos quotidien 11h
        for i in range(1, len(A)):
            rest = (A[i]["start_dt"] - A[i-1]["end_dt"]).total_seconds()/3600.0
            if rest < s.MIN_DAILY_REST_HOURS - 1e-6:
                violations.append(ScheduleViolation(
                    agent_id=a, type="DAILY_REST", date=A[i]["start_dt"].date(),
                    details=f"Repos {rest:.2f} h entre deux shifts (min {s.MIN_DAILY_REST_HOURS} h)",
                    value=round(rest,2), threshold=s.MIN_DAILY_REST_HOURS
                ))

        # 5) Repos hebdomadaire 35h (approx : meilleure coupure sur semaine ISO)
        # On calcule, pour chaque semaine, l'écart max entre blocs travaillés.
        from collections import defaultdict
        blocks = defaultdict(list)
        for x in A:
            blocks[iso_week_key(x["start_dt"].date())].append((x["start_dt"], x["end_dt"]))
        for wk, intervals in blocks.items():
            intervals.sort()
            max_gap = 0.0
            # gap avant premier et après dernier (vers 7j)
            week_start = intervals[0][0].replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            prev_end = week_start
            for st, en in intervals:
                gap = (st - prev_end).total_seconds()/3600.0
                if gap > max_gap: max_gap = gap
                if en > prev_end: prev_end = en
            # gap final
            max_gap = max(max_gap, (week_end - prev_end).total_seconds()/3600.0)
            if max_gap < s.MIN_WEEKLY_REST_HOURS - 1e-6:
                violations.append(ScheduleViolation(
                    agent_id=a, type="WEEKLY_REST", week=wk,
                    details=f"Repos hebdo max {max_gap:.2f} h (min {s.MIN_WEEKLY_REST_HOURS} h)",
                    value=round(max_gap,2), threshold=s.MIN_WEEKLY_REST_HOURS
                ))

        # 6) Jours consécutifs > 6
        days_sorted = sorted({x["start_dt"].date() for x in A})
        run = 1
        for i in range(1, len(days_sorted)):
            if (days_sorted[i] - days_sorted[i-1]).days == 1:
                run += 1
                if run > s.MAX_CONSECUTIVE_DAYS:
                    violations.append(ScheduleViolation(
                        agent_id=a, type="CONSEC_DAYS", date=days_sorted[i],
                        details=f"{run} jours travaillés d'affilée (> {s.MAX_CONSECUTIVE_DAYS})",
                        value=float(run), threshold=float(s.MAX_CONSECUTIVE_DAYS)
                    ))
            else:
                run = 1

        stats.append(ScheduleStats(
            agent_id=a, total_hours=round(total_hours,2),
            days_worked=days_worked, weeks_counted=len(weekly)
        ))

    return SchedulesCheckResult(
        period_start=period_start, period_end=period_end,
        agents=agents, stats=stats, violations=violations,
        extras={"note": "Contrôles standard ; adaptez les seuils dans la config si nécessaire."}
    )
