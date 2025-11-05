# core/data_io.py
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

try:
    import streamlit as st  # solo estará en runtime de Streamlit
except Exception:
    st = None

# ---------------------------
# Utilidades internas
# ---------------------------
def _as_list(x):
    """
    Convierte a lista sin provocar 'truth value of an array is ambiguous'.
    Soporta: list, tuple, set, numpy.ndarray, strings 'a,b' o '["a","b"]', NaN/None.
    """
    # Contenedores comunes
    if isinstance(x, list):
        return x
    if isinstance(x, (tuple, set)):
        return list(x)

    # numpy arrays / pandas arrays
    try:
        import numpy as np
        if isinstance(x, np.ndarray):
            return x.tolist()
    except Exception:
        pass

    # Nulos explícitos
    if x is None:
        return []

    # NaN numérico (evita pd.isna sobre arrays)
    try:
        if isinstance(x, (float, int)) and pd.isna(x):
            return []
    except Exception:
        pass

    # Strings: intenta literal de Python; si no, separa por coma
    if isinstance(x, str):
        s = x.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
            import ast
            try:
                val = ast.literal_eval(s)
                if isinstance(val, (list, tuple, set)):
                    return list(val)
            except Exception:
                pass
        return [p.strip() for p in s.split(",") if p.strip()]

    # Fallback: devuélvelo como lista de un solo elemento
    return [x]


DEFAULT_LOCAL_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "tops.parquet"
)

def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    int_cols = ["release_year", "runtime", "vote_count"]
    float_cols = ["score_total", "vote_average"]
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in float_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _download(url: str, timeout: int = 60) -> bytes:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content

def load_remote(url: Optional[str] = None) -> pd.DataFrame:
    """Carga desde DATA_URL (Hugging Face)."""
    if url is None and st is not None:
        url = st.secrets.get("DATA_URL")  # definida en Secrets
    if not url:
        raise KeyError("DATA_URL no está definido en secrets ni como argumento.")
    raw = _download(url)
    df = pd.read_parquet(io.BytesIO(raw))  # requiere pyarrow
    return _coerce_types(df)

def load_local(path: Optional[str | Path] = None) -> pd.DataFrame:
    """Fallback local para desarrollo."""
    p = Path(path) if path else DEFAULT_LOCAL_PATH
    if not p.exists():
        # compat con nombre alterno del catálogo si lo usas
        alt = Path(__file__).resolve().parents[1] / "data" / "catalogo_peliculas.parquet"
        p = alt if alt.exists() else p
    if not p.exists():
        raise FileNotFoundError(f"No encuentro el dataset local en: {p}")
    df = pd.read_parquet(p)
    return _coerce_types(df)

# API pública para la app
if st is not None:
    @st.cache_data(show_spinner=False, ttl=3600)
    def get_data(
        url: Optional[str] = None,
        local_path: Optional[str | Path] = None,
        prefer_remote: bool = True,
    ) -> pd.DataFrame:
        try:
            if prefer_remote:
                return load_remote(url)
        except Exception as e:
            st.info(f"No pude descargar DATA_URL, uso copia local. Detalle: {e}")
        return load_local(local_path)
else:
    def get_data(
        url: Optional[str] = None,
        local_path: Optional[str | Path] = None,
        prefer_remote: bool = True,
    ) -> pd.DataFrame:
        if prefer_remote:
            try:
                return load_remote(url)
            except Exception:
                pass
        return load_local(local_path)
