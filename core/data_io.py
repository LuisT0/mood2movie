# core/data_io.py
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import ast
import pandas as pd


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


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Coerciona tipos mínimos usados por la app."""
    out = df.copy()
    if "release_year" in out.columns:
        out["release_year"] = pd.to_numeric(out["release_year"], errors="coerce").astype("Int64")
    if "runtime" in out.columns:
        out["runtime"] = pd.to_numeric(out["runtime"], errors="coerce").astype("Int64")
    if "vote_average" in out.columns:
        out["vote_average"] = pd.to_numeric(out["vote_average"], errors="coerce")
    if "vote_count" in out.columns:
        out["vote_count"] = pd.to_numeric(out["vote_count"], errors="coerce").astype("Int64")
    if "popularity" in out.columns:
        out["popularity"] = pd.to_numeric(out["popularity"], errors="coerce")

    # listas para UI amigable
    if "genres" in out.columns:
        out["genres"] = out["genres"].apply(_as_list)
    if "keywords" in out.columns:
        out["keywords"] = out["keywords"].apply(_as_list)

    # strings clave
    for c in ("title", "mood", "saga_key", "explicacion"):
        if c in out.columns:
            out[c] = out[c].astype(str)

    # score_total puede venir como objeto -> a float
    if "score_total" in out.columns:
        out["score_total"] = pd.to_numeric(out["score_total"], errors="coerce")

    return out


# ---------------------------
# API pública
# ---------------------------
def load_tops_dataset(path: Path | str) -> pd.DataFrame:
    """
    Carga el dataset de tops. Intenta Parquet y cae a CSV si aplica.
    La ruta puede ser absoluta o relativa al repo.
    """
    p = Path(path)
    if not p.exists():
        # intenta resolver relativo a la raíz del repo (../data/… desde core/)
        root = Path(__file__).resolve().parents[1]
        candidate = root / "data" / p.name
        if candidate.exists():
            p = candidate
        else:
            # si le pasaron solo 'tops.parquet', prueba en data/
            candidate2 = root / "data" / "tops.parquet"
            if candidate2.exists():
                p = candidate2

    if not p.exists():
        raise FileNotFoundError(f"No encuentro el dataset en: {path}")

    # Detecta por extensión
    ext = p.suffix.lower()
    if ext in (".parquet", ".pq"):
        df = pd.read_parquet(p)
    elif ext == ".csv":
        df = pd.read_csv(p, encoding="utf-8")
    else:
        # intenta primero parquet y si falla, CSV
        try:
            df = pd.read_parquet(p)
        except Exception:
            df = pd.read_csv(p, encoding="utf-8")

    df = _coerce_types(df)
    return df


def ensure_required_columns(df: pd.DataFrame, required: List[str]) -> List[str]:
    """
    Revisa que existan columnas requeridas; devuelve la lista de faltantes.
    No levanta excepción (eso lo hace la UI para dar mensaje bonito).
    """
    have = set(df.columns)
    missing = [c for c in required if c not in have]
    return missing


# ---------------------------
# Helpers opcionales (útiles en tests/local)
# ---------------------------
def load_catalog(path: Path | str) -> pd.DataFrame:
    """
    Carga el catálogo completo (si lo usas en depuración local).
    """
    p = Path(path)
    if not p.exists():
        root = Path(__file__).resolve().parents[1]
        candidate = root / "data" / "catalogo_peliculas.parquet"
        if candidate.exists():
            p = candidate
    if not p.exists():
        raise FileNotFoundError(f"No encuentro el catálogo en: {path}")

    if p.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, encoding="utf-8")
    return _coerce_types(df)