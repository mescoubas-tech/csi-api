# app/services/datetime_utils.py
from __future__ import annotations
import pandas as pd
from typing import Optional

TIME_RANGE_REGEX = r'(?P<start>\d{1,2}:\d{2})\s*[-–à]\s*(?P<end>\d{1,2}:\d{2})'

def ensure_start_end_columns(df: pd.DataFrame, horaire_col: Optional[str] = "horaire",
                             start_col: str = "start", end_col: str = "end") -> pd.DataFrame:
    if start_col in df.columns and end_col in df.columns:
        return df
    if horaire_col and horaire_col in df.columns:
        times = df[horaire_col].astype(str).str.extract(TIME_RANGE_REGEX, expand=True)
        if start_col not in df.columns:
            df[start_col] = pd.NA
        if end_col not in df.columns:
            df[end_col] = pd.NA
        df.loc[:, [start_col, end_col]] = times
    else:
        if start_col not in df.columns:
            df[start_col] = pd.NA
        if end_col not in df.columns:
            df[end_col] = pd.NA
    return df

def build_start_end_dt(df: pd.DataFrame, date_col: str = "date",
                       start_col: str = "start", end_col: str = "end",
                       start_dt_col: str = "start_dt", end_dt_col: str = "end_dt",
                       dayfirst: bool = True) -> pd.DataFrame:
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=dayfirst)
    else:
        df[date_col] = pd.NaT

    if start_col not in df.columns:
        df[start_col] = pd.NA
    if end_col not in df.columns:
        df[end_col] = pd.NA

    date_str = df[date_col].dt.strftime("%Y-%m-%d")
    df[start_dt_col] = pd.to_datetime((date_str.fillna("") + " " + df[start_col].astype(str)).str.strip(), errors="coerce")
    df[end_dt_col] = pd.to_datetime((date_str.fillna("") + " " + df[end_col].astype(str)).str.strip(), errors="coerce")

    mask_rollover = df[end_dt_col].notna() & df[start_dt_col].notna() & (df[end_dt_col] < df[start_dt_col])
    df.loc[mask_rollover, end_dt_col] = df.loc[mask_rollover, end_dt_col] + pd.Timedelta(days=1)
    return df

def ensure_datetimes_pipeline(df: pd.DataFrame, date_col: str = "date",
                              horaire_col: Optional[str] = "horaire",
                              start_col: str = "start", end_col: str = "end",
                              start_dt_col: str = "start_dt", end_dt_col: str = "end_dt",
                              dayfirst: bool = True) -> pd.DataFrame:
    df = ensure_start_end_columns(df, horaire_col=horaire_col, start_col=start_col, end_col=end_col)
    df = build_start_end_dt(df, date_col=date_col, start_col=start_col, end_col=end_col,
                            start_dt_col=start_dt_col, end_dt_col=end_dt_col, dayfirst=dayfirst)
    return df
