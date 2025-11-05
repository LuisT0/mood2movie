Criterios de Ranking — Mood2Movie

Versión de reglas: v1.0
Fecha: 2025-10-14
Propósito: definir, de forma operativa y auditable, cómo se calcula el score_total por mood, qué filtros aplican, cómo se normalizan las señales, cómo se resuelven empates y cómo se garantiza diversidad por saga.

1) Contrato de datos (columnas requeridas)
La app y el pipeline asumen estas columnas en el catálogo/tops:
title (str)
release_year (int)
genres (list[str] o str separada por comas)
keywords (list[str] o str separada por comas)
runtime (int, minutos)
vote_average (float, 0–10)
vote_count (int)
popularity (float, TMDB u origen equivalente)
saga_key (str) — si falta, se deriva de belongs_to_collection.name o heurística del título
mood (str) — solo en el consolidado
Señales derivadas en tops: match_raw, match_norm, recencia, rating_norm, votes_norm, pop_norm, score_total, explicacion (texto)

2) Fórmula general del score
Todas las señales se llevan a [0, 1].
El puntaje final por película es:
score_total = w_match * match_norm
            + w_recency * recencia
            + w_rating * rating_norm
            + w_votes  * votes_norm
            + w_pop    * pop_norm
Desempate (en ese orden):
score_total descendente
pop_norm descendente
title ascendente (determinismo)
Diversidad por saga (Top-N):
Se aplica per_group_max = 1 por saga_key dentro de cada Top-N de mood.
En el consolidado global puede aplicarse de-duplicado por saga_key si se desea variedad total.

3) Definición exacta de señales
Match (géneros + keywords)
Definición:
match_raw = (#grupos_boost_genero_matcheados) + (#grupos_boost_keyword_matcheados)
Un “grupo” es un set definido en config; si la película contiene cualquier elemento del set, suma 1.
Normalización: match_norm = min-max(match_raw) sobre las candidatas del mood.
Recencia
recencia = min-max(release_year) con floor = 1980 (años menores se clippean a 1980).
Intuición: más reciente → mayor valor.
Rating (con shrinkage bayesiano)
rating_shrunk = (v/(v+k))*r + (k/(v+k))*global_mean
r = vote_average, v = vote_count, global_mean = 6.8, k = k_votes (ver tabla por mood).
rating_norm = min-max(rating_shrunk) en candidatas.
Votos (confianza)
votes_norm = v / (v + k_votes) ∈ [0,1].
Popularidad
pop_norm = min-max(popularity) en candidatas.
Nota: “min-max” significa llevar la señal a [0,1] usando el mínimo y máximo dentro del set de candidatas. Si min=max, se usa 0.5 para toda la columna (caso degenerado).

4) Pesos y filtros por mood
4.1 Pesos (suman 1.0 por mood)
Mood	w_match	w_recency	w_rating	w_votes	w_pop
accion_thriller	0.45	0.10	0.20	0.10	0.15
drama_romance	0.35	0.10	0.30	0.15	0.10
cozy_ligera	0.40	0.10	0.25	0.10	0.15
suspenso_misterio	0.45	0.10	0.25	0.10	0.10
4.2 Filtros duros (candidatas) y k_votes
Mood	runtime_min	runtime_max	min_votes	k_votes
accion_thriller	85	180	50	250
drama_romance	80	180	20	200
cozy_ligera	75	120	10	150
suspenso_misterio	80	160	30	220
Si un mood queda vacío tras filtros, se sugiere relajar min_votes o ampliar runtime.

5) Reglas de match por mood (esquema)
Cada mood define:
genre_sets.must_any (opcional): al menos un set debe cumplirse para ser candidata.
genre_sets.boost_any: sets que suman al match_raw.
keyword_sets.boost_any: sets que suman al match_raw.
Ejemplos de intención (resumen):
accion_thriller: prioriza Action/Thriller y keywords de acción/persecución/espionaje.
drama_romance: prioriza Drama/Romance y keywords de relaciones, coming-of-age, etc.
cozy_ligera: busca Comedy/Family/Romance y keywords “feel-good”. (suele no usar must_any para amplitud)
suspenso_misterio: Thriller/Mystery + keywords de investigación/whodunit.
Los sets exactos viven en la config del notebook/módulo. Este documento define el comportamiento, no repite el código.

6) Penalizaciones (si se activan)
(Actualmente el MVP no aplica penalizaciones duras; el control se hace vía filtros y diversidad. Este bloque deja el marco si se habilitan en v2.)
Duración fuera del mood (p.ej., runtime > 160 para cozy_ligera):
Opción A: restar Δ al match_raw antes de normalizar.
Opción B: restar λ al score_total después de ponderar.
Repetición de saga en top-3: ya mitigado por per_group_max=1; no se aplica penalización adicional.
Si se activan, documentar magnitud (Δ/λ) y punto de aplicación (antes/después) en este archivo y en el changelog.

7) Diversidad, empates y determinismo
Diversidad intra-mood: per_group_max = 1 por saga_key en el Top-N.
Diversidad global (opcional): en el consolidado, de-duplicar por saga_key.
Empates: score_total desc → pop_norm desc → title asc.
Determinismo: fijar semilla cuando corresponda en procesos con aleatoriedad (no aplica en este ranking, pero sí en muestreos).

8) QA mínimo viable
Antes de persistir tops.parquet/csv:
No nulos: title, release_year, genres no deben contener NaN en los tops.
Rango de score: score_total ∈ [0,1].
Variedad por mood: cada Top-10 debe tener ≥ 8 saga_key únicos (si hay menos, revisar filtros/pesos o per_group_max).
Consolidado no vacío y sin columnas faltantes respecto al Contrato de datos.

9) Calibración con “golden set”
Para cada mood, mantener 5–10 títulos “ancla” que deberían caer alto.
Si no aparecen, ajustar:
Pesos (w_rating/w_votes vs w_pop/w_recency).
Filtros (min_votes, runtime)
Sets de genres/keywords (ruido o falta de cobertura)
Dejar el golden set documentado en docs/mood_rules.md.

10) Cómo agregar un nuevo mood (procedimiento)
Definir sets en config: genre_sets y keyword_sets (con must_any si aplica y boost_any).
Marcar filtros (tabla de runtime_min/max, min_votes, k_votes) y pesos (w_*).
Registrar el mood en el diccionario de configs del pipeline.
Correr build_all_moods_tops y pasar QA.
Documentar en este archivo la nueva fila de pesos/filtros y el rationale en mood_rules.md.

11) Versionado y cambios
v1.0 (2025-10-14)
Definición formal de señales y normalización a [0,1].
Pesos/filtros por los 4 moods iniciales.
Desempate y diversidad documentados.
QA mínimo y procedimiento de golden set.
Penalizaciones desactivadas en MVP (marco listo para v2).