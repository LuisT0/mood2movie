# app/streamlit_app.py
import sys, os
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st

# --- bootstrapping para imports cuando el entrypoint está en /app ---
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.data_io import get_data

DATA_DIR = ROOT / "data"
TOPS_PATH = DATA_DIR / "tops.parquet"


def movie_key(row):
    """Llave para seleccionar; usa id si existe, si no title|year|mood."""
    mid = row.get("id")
    if pd.notna(mid):
        return f"id::{int(mid)}"
    title = str(row.get("title") or "").strip()
    year = str(int(row.get("release_year"))) if pd.notna(row.get("release_year")) else "NA"
    mood = str(row.get("mood") or "")
    return f"ty::{title}|{year}|{mood}"

def select_movie(key: str):
    st.session_state["sel_movie_key"] = key
    
    st.rerun()

def clear_selection():
    st.session_state.pop("sel_movie_key", None)

# ---------- Config UI ----------
st.set_page_config(page_title="Mood2Movie", page_icon="🎬", layout="wide")

def show_poster(url: str):
    if url:
        st.image(url, use_container_width=True)

def _safe_isna(x):
    
    try:
        
        import numpy as np
        if isinstance(x, (list, tuple, set)) or (hasattr(np, "ndarray") and isinstance(x, np.ndarray)):
            return False
        return pd.isna(x)
    except Exception:
        return False

def _ensure_list_ui(x):
    """
    Convierte x a lista para UI. Soporta list/tuple/set/ndarray/str/dict/NaN.
    - Si viene str 'a, b' -> ['a','b']
    - Si viene str '["a","b"]' -> ['a','b']
    """
    if isinstance(x, list):
        return x
    if isinstance(x, (tuple, set)):
        return list(x)
    try:
        import numpy as np
        if isinstance(x, np.ndarray):
            return x.tolist()
    except Exception:
        pass
    if x is None or _safe_isna(x):
        return []
    if isinstance(x, dict):
        return [str(x.get("name", x)).strip()]
    if isinstance(x, str):
        s = x.strip()
        # intenta parsear lista literal
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
            import ast
            try:
                val = ast.literal_eval(s)
                if isinstance(val, (list, tuple, set)):
                    return [str(v).strip() for v in val if str(v).strip()]
            except Exception:
                pass
        return [p.strip() for p in s.split(",") if p.strip()]
    return [x]

@st.cache_data
def load_tops(path: Path) -> pd.DataFrame:
    with st.spinner("Cargando datos…"):
        df = get_data()

    # Normaliza tipos conflictivos
    for c in ["genres", "keywords"]:
        if c in df.columns:
            df[c] = df[c].apply(_ensure_list_ui)

    # Coerciones suaves útiles para los filtros
    if "release_year" in df.columns:
        df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce")
    if "runtime" in df.columns:
        df["runtime"] = pd.to_numeric(df["runtime"], errors="coerce")
    if "vote_count" in df.columns:
        df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce")
    if "vote_average" in df.columns:
        df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce")

    needed = ["title","release_year","mood","score_total"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise RuntimeError(f"Faltan columnas en tops: {missing}")
    return df

def chip(txt):
    return f"<span style='padding:2px 8px;border-radius:12px;background:#222; color:#ddd; font-size:0.75rem;'>{txt}</span>"

def _genres_inline(gs, max_items=3):
    if isinstance(gs, (list, tuple, set)):
        gs = list(gs)[:max_items]
        return ", ".join(str(g) for g in gs) if gs else "—"
    return str(gs) if pd.notna(gs) else "—"

def _snippet(txt, n=180):
    if not txt or not isinstance(txt, str):
        return ""
    return (txt if len(txt) <= n else txt[:n].rsplit(" ", 1)[0] + "…").strip()

def render_card(row: pd.Series) -> bool:
    title = str(row.get("title") or "Título desconocido").strip()
    year  = int(row.get("release_year") or 0) if pd.notna(row.get("release_year")) else None
    gens  = _genres_inline(row.get("genres"), 2)

    meta = f"{year} • {gens}" if year else gens
    overview = row.get("overview")
    if overview and isinstance(overview, str) and overview.strip():
        body = _snippet(overview, n=220)
    else:
        rt = int(row.get("runtime") or 0) if pd.notna(row.get("runtime")) else None
        rt_tag = f"{rt} min" if rt else ""
        body = f"{meta}. {rt_tag}".strip()

    poster = row.get("poster_url_w342")

    with st.container():
        if poster:
            show_poster(poster)
        st.markdown(f"**{title}**")
        st.caption(meta)
        if body:
            st.write(body)

        k = str(row.get("movie_key"))
        if st.button("Ver detalle", key=f"btn_det_{k}", use_container_width=True):
            st.session_state["sel_movie_key"] = k
            st.rerun() 
            return True
    return False


def detail_view(row: pd.Series, df_context: pd.DataFrame):
    # Header
    title = str(row.get("title") or "Título desconocido")
    year  = int(row.get("release_year") or 0) if pd.notna(row.get("release_year")) else None
    st.markdown(f"### {title} {f'({year})' if year else ''}")

    col1, col2 = st.columns([1, 2])
    with col1:
        poster = row.get("poster_url_w342")
        if poster:
            show_poster(poster)
        # métricas
        va = row.get("vote_average")
        vc = row.get("vote_count")
        rt = row.get("runtime")
        if pd.notna(va) or pd.notna(vc) or pd.notna(rt):
            st.markdown("**Ficha**")
            if pd.notna(va): st.write(f"⭐️ Rating: {float(va):.1f}")
            if pd.notna(vc): st.write(f"🗳️ Votos: {int(vc)}")
            if pd.notna(rt): st.write(f"⏱️ Duración: {int(rt)} min")
        gens = _genres_inline(row.get("genres"), 5)
        if gens and gens != "—":
            st.write(f"🎭 Géneros: {gens}")

    with col2:
        ov = row.get("overview")
        if ov and isinstance(ov, str) and ov.strip():
            st.markdown("**Sinopsis**")
            st.write(ov)
        # Explicabilidad (ahora sí, aquí)
        exp = row.get("explicacion")
        if exp and isinstance(exp, str) and exp.strip():
            st.markdown("**¿Por qué aparece aquí?**")
            st.write(exp)
        # score
        sc = row.get("score_total")
        if pd.notna(sc):
            st.caption(f"Score: {float(sc):.3f}")

    st.divider()

    # Relacionadas (mismo mood y al menos un género en común)
    mood = row.get("mood")
    rel = df_context[df_context["mood"] == mood].copy()
    def _overlap(g1, g2):
        if not isinstance(g1, (list, set, tuple)) or not isinstance(g2, (list, set, tuple)):
            return False
        return len(set(g1) & set(g2)) > 0
    rel = rel[rel["movie_key"] != row["movie_key"]]
    if "genres" in rel.columns:
        rel = rel[rel["genres"].apply(lambda g: _overlap(g, row.get("genres")))]
    rel = rel.sort_values("score_total", ascending=False).head(12)

    if len(rel):
        st.markdown("**Te podría gustar**")
        cols = st.columns(4)
        for i, (_, r2) in enumerate(rel.iterrows()):
            with cols[i % 4]:
                if r2.get("poster_url_w342"):
                    show_poster(r2["poster_url_w342"])
                st.caption(str(r2.get("title") or "—"))
                if st.button("Ver detalle", key=f"btn_det_rel_{r2['movie_key']}", use_container_width=True):
                    st.session_state["sel_movie_key"] = r2["movie_key"]
                    st.rerun()

    # volver
    if st.button("← Volver al grid", use_container_width=True):
        st.session_state["sel_movie_key"] = None
        st.rerun()


def controls(df: pd.DataFrame) -> dict:
    # --- helpers ---
    def _pretty_mood(k: str) -> str:
        mapa = {
            "accion_thriller": "Acción / Thriller",
            "drama_romance": "Drama / Romance",
            "cozy_ligera": "Cozy / Ligera",
            "suspenso_misterio": "Suspenso / Misterio",
        }
        return mapa.get(k, k.replace("_", " ").title())

    def _reverse_pretty(v: str, keys):
        inv = { _pretty_mood(k): k for k in keys }
        return inv.get(v, keys[0])

    # --- defaults derivados del dataset ---
    years = df["release_year"].dropna().astype(int)
    y_min, y_max = (int(years.min()), int(years.max())) if len(years) else (2000, 2025)

    rts = df["runtime"].dropna().astype(int)
    rt_min, rt_max = (int(rts.min()), int(rts.max())) if len(rts) else (60, 240)

    moods = sorted(df["mood"].unique()) or ["accion_thriller"]

    default_state = {
        "mood": moods[0],
        "yr": (y_min, y_max),
        "rt": (max(60, rt_min), min(210, rt_max)),
        "min_votes": 30,
        "one_per_saga": True,
        "q": "",
    }

    # -------- versión de widgets --------
    if "controls_version" not in st.session_state:
        st.session_state["controls_version"] = 0
    ver = st.session_state["controls_version"]

    # -------- HARD RESET antes de crear widgets --------
    if st.session_state.get("do_reset_controls", False):
        # estado lógico a defaults
        st.session_state["controls_state"] = default_state.copy()

        # limpiar keys del render anterior (versión previa) para forzar re-mount visual
        prev = ver - 1 if ver > 0 else None
        if prev is not None:
            for k in [
                f"ctrl_mood_display_{prev}",
                f"ctrl_years_{prev}",
                f"ctrl_runtime_{prev}",
                f"ctrl_min_votes_{prev}",
                f"ctrl_one_per_saga_{prev}",
                f"ctrl_q_{prev}",
            ]:
                if k in st.session_state:
                    del st.session_state[k]

        st.session_state.pop("do_reset_controls", None)

    # estado lógico vivo
    state = st.session_state.setdefault("controls_state", default_state.copy())

    # === Widgets con keys versionadas ===
    st.sidebar.markdown("**¿Qué tienes ganas de ver?**")
    mood_display_opts = [_pretty_mood(k) for k in moods]
    current_pretty = _pretty_mood(state["mood"])
    idx = mood_display_opts.index(current_pretty) if current_pretty in mood_display_opts else 0
    mood_display = st.sidebar.selectbox(
        "Mood",
        mood_display_opts,
        index=idx,
        label_visibility="collapsed",
        key=f"ctrl_mood_display_{ver}",
        help="Elige un mood. Nosotros hacemos la magia."
    )
    state["mood"] = _reverse_pretty(mood_display, moods)

    st.sidebar.markdown("**¿Qué tan moderna?**")
    yr = st.sidebar.slider(
        "Rango de años",
        y_min, y_max,
        value=tuple(state["yr"]),
        key=f"ctrl_years_{ver}",
        help="Arrastra para elegir el rango de años."
    )
    st.sidebar.caption(f"{yr[0]} — {yr[1]}")
    state["yr"] = yr

    st.sidebar.markdown("**¿Qué tan larga?**")
    rt = st.sidebar.slider(
        "Duración (minutos)",
        max(60, rt_min), min(240, rt_max),
        value=tuple(state["rt"]),
        key=f"ctrl_runtime_{ver}",
        help="Duración en minutos. Tip: < 100 min si tienes prisa."
    )
    st.sidebar.caption(f"{rt[0]} — {rt[1]} min")
    state["rt"] = rt

    st.sidebar.markdown("**¿Alguna en mente?**")
    q = st.sidebar.text_input(
        "Escribe parte del título (opcional)",
        value=state["q"],
        key=f"ctrl_q_{ver}",
        placeholder="Ej.: bourne, protector, hermanas"
    )
    state["q"] = q

    with st.sidebar.expander("Refina tu búsqueda", expanded=False):
        one_per_saga = st.toggle(
            "Evitar repetir sagas (diversidad)",
            value=state["one_per_saga"],
            key=f"ctrl_one_per_saga_{ver}",
            help="Muestra a lo mucho 1 título por franquicia."
        )
        state["one_per_saga"] = one_per_saga

    st.sidebar.divider()
    if st.sidebar.button("🔄 Resetear filtros", key=f"btn_reset_{ver}", use_container_width=True):
        st.session_state["controls_version"] = ver + 1   # sube versión → nuevas keys
        st.session_state["do_reset_controls"] = True     # repone defaults lógicos
        st.rerun()

    return dict(
        mood=state["mood"],
        yr=state["yr"],
        rt=state["rt"],
        min_votes=state["min_votes"],
        one_per_saga=state["one_per_saga"],
        q=state["q"],
    )

def apply_filters(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()

    # 1) Mood
    out = out[out["mood"] == cfg["mood"]]

    # 2) Año
    y0, y1 = cfg["yr"]
    out = out[out["release_year"].fillna(0).between(int(y0), int(y1), inclusive="both")]

    # 3) Duración
    r0, r1 = cfg["rt"]
    out = out[out["runtime"].fillna(0).between(int(r0), int(r1), inclusive="both")]

    # 4) Votos mínimos 
    mv = int(cfg.get("min_votes", 0) or 0)
    out = out[out["vote_count"].fillna(0).astype(int) >= mv]

    # 5) Búsqueda por título
    q = (cfg.get("q") or "").strip()
    if q:
        out = out[out["title"].str.contains(q, case=False, na=False)]

    # 6) 1 por saga (diversidad)
    if cfg.get("one_per_saga", False) and "saga_key" in out.columns:
        out = (out.sort_values(["score_total", "pop_norm", "title"], ascending=[False, False, True])
                  .drop_duplicates(subset="saga_key", keep="first"))

    # 7) Orden final
    out = out.sort_values(["score_total", "pop_norm", "title"], ascending=[False, False, True])
    return out.reset_index(drop=True)

def grid(df):
    # grid responsivo simple
    n = len(df)
    if n == 0:
        st.info("No hay resultados con los filtros actuales.")
        return None
    cols = st.columns(4)
    selected = None
    for i, (_, row) in enumerate(df.iterrows()):
        with cols[i % 4]:
            if render_card(row):
                selected = row
    return selected

# =========================
# Página
# =========================

st.title("Mood2Movie 🎬")
st.caption("Elige cómo te sientes, nosotros encontramos la historia perfecta. Porque ver cine también es cuestión de *mood.*")

# carga
try:
    df = load_tops(TOPS_PATH)
except Exception as e:
    st.error(f"No pude cargar el dataset de tops: {e}")
    st.stop()

def _mk_movie_key(r):
    for c in ["tmdb_id", "imdb_id", "id"]:
        if c in r and pd.notna(r[c]):
            return f"{c}:{r[c]}"
    # fallback estable
    y = int(r.get("release_year") or 0)
    saga = r.get("saga_key") or ""
    return f"{str(r.get('title') or '?')}_{y}_{saga}"

def ensure_movie_keys(df: pd.DataFrame) -> pd.DataFrame:
    if "movie_key" in df.columns:
        return df
    out = df.copy()
    out["movie_key"] = out.apply(_mk_movie_key, axis=1)
    return out

df = ensure_movie_keys(df)

cfg = controls(df)

sub = apply_filters(df, cfg)
c1, c2, c3 = st.columns(3)
with c1: st.metric("Películas en vista", len(sub))
with c2:
    sagas = sub["saga_key"].nunique() if "saga_key" in sub.columns else len(sub)
with c3:
    if len(sub):
        ymin, ymax = int(sub["release_year"].min()), int(sub["release_year"].max())
        st.metric("Año (min–max)", f"{ymin}–{ymax}")
    else:
        st.metric("Año (min–max)", "—")

# Grid + detalle
# Grid + detalle
sel_key = st.session_state.get("sel_movie_key")

if not sel_key:
    grid(sub.head(48))  # render cards
else:
    # encontrar la fila seleccionada usando la MISMA llave que pintamos en las tarjetas
    def row_matches_key(r):
        return str(r.get("movie_key")) == str(sel_key)

    match = sub[sub.apply(row_matches_key, axis=1)]

    if match.empty:
        st.warning("No encontré la película seleccionada. Volviendo a la grilla.")
        clear_selection()
        st.rerun()  # refresco limpio
    else:
        st.divider()
        col_back, _ = st.columns([1, 9])
        with col_back:
            st.button("← Volver", on_click=clear_selection)
        detail_view(match.iloc[0], sub)
