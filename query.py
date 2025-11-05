# core/query.py
from __future__ import annotations

import re
from typing import Iterable, Tuple, Optional

import pandas as pd


def _coerce_numeric(s: pd.Series) -> pd.Series:
    """Asegura numérico para filtros; no rompe NaNs."""
    return pd.to_numeric(s, errors="coerce")


def _normalize_text(s: pd.Series) -> pd.Series:
    """Limpia texto para búsqueda (lower + strip). Maneja NaNs."""
    return s.fillna("").astype(str).str.lower().str.strip()


def _apply_year_filter(df: pd.DataFrame, year_range: Tuple[int, int]) -> pd.DataFrame:
    if "release_year" not in df.columns:
        return df
    y = _coerce_numeric(df["release_year"])
    return df[(y >= year_range[0]) & (y <= year_range[1])]


def _apply_runtime_filter(df: pd.DataFrame, runtime_range: Tuple[int, int]) -> pd.DataFrame:
    if "runtime" not in df.columns:
        return df
    r = _coerce_numeric(df["runtime"])
    return df[(r >= runtime_range[0]) & (r <= runtime_range[1])]


def _apply_min_votes(df: pd.DataFrame, min_votes: int) -> pd.DataFrame:
    if "vote_count" not in df.columns:
        return df
    v = _coerce_numeric(df["vote_count"])
    return df[v >= min_votes]


def _apply_search(df: pd.DataFrame, search_text: str) -> pd.DataFrame:
    """Búsqueda simple por título; si viene vacío, no filtra."""
    q = (search_text or "").strip().lower()
    if not q:
        return df
    if "title" not in df.columns:
        return df
    # Coincidencia contains case-insensitive; escapamos regex por si hay caracteres raros
    pattern = re.escape(q)
    mask = _normalize_text(df["title"]).str.contains(pattern, na=False)
    return df[mask]


def _dedupe_by_saga(df: pd.DataFrame) -> pd.DataFrame:
    """Mantiene 1 por saga_key priorizando score_total > popularity > title."""
    if "saga_key" not in df.columns or df.empty:
        return df
    # Orden de prioridad: igual que en la UI/pipeline
    order_cols = [c for c in ["score_total", "popularity", "title"] if c in df.columns]
    ascending = [False, False, True][: len(order_cols)]
    ordered = df.sort_values(order_cols, ascending=ascending)
    return ordered.drop_duplicates(subset=["saga_key"], keep="first")


def filter_view(
    df_all: pd.DataFrame,
    mood: str,
    year_range: Tuple[int, int],
    runtime_range: Tuple[int, int],
    min_votes: int = 0,
    one_per_saga: bool = True,
    search_text: str = "",
) -> pd.DataFrame:
    """
    Devuelve la vista filtrada para la app:
      - mood (obligatorio)
      - rango de año (release_year)
      - rango de duración (runtime)
      - mínimo de votos (vote_count)
      - texto de búsqueda en título
      - toggle 1 por saga (de-duplicado por saga_key)
    No altera el orden final (la UI ordena), pero respeta el contrato de columnas.
    """
    if df_all is None or df_all.empty:
        return pd.DataFrame()

    # --- 1) Subset por mood ---
    if "mood" not in df_all.columns:
        # Si no existiera (no debería), devuelve vacío para un fallo explícito en la UI
        return pd.DataFrame()
    sub = df_all[df_all["mood"].astype(str).str.lower() == str(mood).lower()].copy()

    if sub.empty:
        return sub

    # --- 2) Filtros duros ---
    sub = _apply_year_filter(sub, year_range)
    sub = _apply_runtime_filter(sub, runtime_range)
    sub = _apply_min_votes(sub, int(min_votes))

    if sub.empty:
        return sub

    # --- 3) Búsqueda por título ---
    sub = _apply_search(sub, search_text)

    if sub.empty:
        return sub

    # --- 4) De-duplicado por saga (si se solicita) ---
    if one_per_saga:
        sub = _dedupe_by_saga(sub)

    # --- 5) Limpieza final de tipos básicos (por si entró algo raro) ---
    # No forzamos orden aquí; lo hace la UI con columnas de confianza
    # Saneamos algunas columnas para evitar warnings de Streamlit
    for col in ("release_year", "runtime", "vote_count"):
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce").astype("Int64")

    # Reset index para visual estable
    return sub.reset_index(drop=True)