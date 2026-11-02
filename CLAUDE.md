# Liga MX · Apertura 2026 · Predictor

Sistema de predicción de partidos y recomendación de apuestas para Liga MX, usando simulación Monte Carlo (Poisson + Dixon-Coles). Streamlit + Supabase. Mismo enfoque que un predictor previo del Mundial 2026 del mismo autor, adaptado a liga regular con Liguilla.

## Arquitectura (6 módulos)

- **`liga_mx_predictor_skeleton.py`** — datos base: `EQUIPOS`, `ELO`, `ALTITUD_EQUIPO`, `PARTIDOS` (calendario + resultados), `HORARIOS_PARTIDO`, `ARBITROS_LIGA_MX`, `TARJETAS_EQUIPO_LIGAMX`/`TARJETAS_EQUIPO_APERTURA`, `CORNERS_EQUIPO`, `DATOS_REALES_LIGAMX` (tarjetas/córners reales por partido jugado). Es la única fuente de verdad para resultados y calendario.
- **`liga_mx_motor_poisson.py`** — motor de goles por defecto (`MOTOR_GOLES = "poisson_mle"` en `liga_mx_algoritmo.py`): Poisson/Dixon-Coles ajustado por máxima verosimilitud con shrinkage (ridge 5), Clausura 2026 como prior (peso 0.6) y decaimiento 0.05/jornada; localía y ρ salen de los datos. Reemplaza al cálculo heredado (FUERZA_* + EMA + split local/visita + ×1.12 + altitud), que se conserva con `motor="heredado"` solo para comparar.
- **`liga_mx_walkforward.py`** — backtest a ciegas sobre el Apertura (cada jornada con solo las anteriores). Cualquier cambio al motor se mide aquí antes de subirlo (`python3 liga_mx_walkforward.py`); el análisis semanal lo publica en el resumen de Actions.
- **`liga_mx_elo_update.py`** — recalibra Elo y Fuerza Ataque/Defensa jornada a jornada reproduciendo `PARTIDOS` desde cero (EMA, α=0.15). No se toca casi nunca.
- **`liga_mx_algoritmo.py`** — el motor: `calcular_lambdas()`, `simular_partido()` (Monte Carlo, 10M sims), `analizar_apuestas()` (qué recomendar), `simular_jornada_completa()`, `armar_parlay()`. Aquí vive casi toda la lógica de negocio.
- **`liga_mx_supabase.py`** — persistencia: guardar/cargar predicciones y apuestas, `calcular_sesgo_por_equipo()`, `calcular_brier_score()`, `calcular_calibracion_por_bin()`, `calcular_mercados_suspendidos()` (auto-retroalimentación).
- **`liga_mx_cuotas.py`** — integración con The Odds API para value betting. `sport_key` confirmado: `soccer_mexico_ligamx`.
- **`app.py`** — interfaz Streamlit, 8 tabs. Todo el HTML/CSS está inline en f-strings, sigue ese patrón para cualquier tarjeta nueva.

## Flujo de trabajo más común: cargar resultado de una jornada

Cuando el usuario pegue una página de Sofascore (o texto con resultado de un partido):

1. Extraer: equipos, marcador, tarjetas amarillas por equipo, córners por equipo, rojas, árbitro central si aparece.
2. En `liga_mx_predictor_skeleton.py`:
   - Actualizar la tupla en `PARTIDOS`: cambiar el `None` de resultado por `(goles_local, goles_visita)`, y el `None` de árbitro por el nombre si se tiene (formato SIN acentos: "Cesar" no "César", ver convención abajo).
   - Agregar entrada a `DATOS_REALES_LIGAMX` con clave `"Local_Visitante"` (usando los nombres internos de `EQUIPOS`, no los de Sofascore) y valor `{"am": total_amarillas, "co": total_corners, "ro": total_rojas}`.
   - Si el árbitro es nuevo (no está en `ARBITROS_LIGA_MX`), agregarlo con `ARBITRO_DEFAULT` como placeholder y un comentario explicando que es debut sin ficha confirmada — nunca inventar un promedio.
3. Validar con `python3 -c "import ast; ast.parse(open('liga_mx_predictor_skeleton.py').read())"`.
4. Confirmar con una consulta rápida que el partido se refleja en `tabla_actual_real()` y que `detectar_jornada_actual()` avanza cuando la jornada se completa.
5. Commit y push.

**Nunca hardcodear un `sport_key`, promedio de árbitro, o nombre de equipo sin confirmarlo con una fuente real** — mejor dejar un placeholder documentado que adivinar.

## Convenciones de nombres (importante, causa bugs si se ignora)

- Nombres de equipo internos SIN acentos: `America`, `Queretaro`, `Leon`, `Atletico San Luis`, `FC Juarez`, `Atlante` (no "Atlante FC"), `Pumas UNAM` (no solo "Pumas").
- Nombres de árbitro SIN acentos también: `Cesar Arturo Ramos Palazuelos`, no "César".
- The Odds API SÍ usa acentos y variantes distintas — por eso existe `liga_mx_cuotas.emparejar_equipo()`, que normaliza. Si se agrega una fuente de datos externa nueva, replicar ese patrón de emparejamiento en vez de asumir que los nombres calzan igual.

## Reglas del modelo que no deben romperse sin discutirlo primero

- **Umbral dinámico** (`_umbral_dinamico()` en `liga_mx_algoritmo.py`): 90% en jornada 0 → 80% con 10+ PJ promedio del equipo. No es un umbral fijo — si algo parece "no estar recomendando nada", revisar cuántos PJ lleva el equipo antes de asumir que está roto.
- **Una sola línea por rubro** en `analizar_apuestas()` (Total Goles, Tarjetas, Córners, etc.): decisión explícita del usuario — mostrar solo la de mayor confianza dentro de cada rubro, pero SÍ permitir que rubros distintos aparezcan juntos en el mismo partido. No volver a la versión "todas las líneas sin deduplicar" sin que el usuario lo pida explícitamente (ya se intentó y se revirtió).
- **Value betting solo sobre 1X2 y solo si ya pasó el umbral de confianza** — no exponer un mercado aparte de "underdogs con valor". Decisión explícita del usuario, documentada en el docstring de `analizar_apuestas()`.
- **Sesgo por equipo** (`calcular_sesgo_por_equipo()`): requiere mínimo 8 partidos evaluados por equipo/rol (local o visita) antes de aplicar corrección. No bajar ese mínimo sin confirmarlo.
- Cualquier factor nuevo en `calcular_lambdas()` debe ser **opcional con default seguro** (`None` o `1.0`) para no romper retrocompatibilidad con llamadas existentes.

## Validación obligatoria antes de dar por terminado un cambio

```bash
python3 -c "import ast; ast.parse(open('ARCHIVO.py').read())"
```

Para cambios en `app.py`, además correr un test de ejecución real (no solo sintaxis):

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('app.py')
at.run(timeout=60)
assert not at.exception, at.exception
```

Y si se modificó un botón, simular el click:

```python
btn = [b for b in at.button if b.label == '⚽ Simular Jornada'][0]
btn.click().run(timeout=120)
assert not at.exception, at.exception
```

## Errores ya cometidos — no repetir

- La app simulaba y guardaba partidos ya jugados al abrirlos (con el resultado ya dentro de Elo/motor), sobrescribiendo la predicción a ciegas. Ahora `guardar_prediccion()`/`guardar_apuestas()` no escriben si el partido ya empezó, y `cargar_historial_*()` descartan filas guardadas después del arranque. No quitar ese filtro.
- La isotónica se ajusta sobre `confianza_cruda` y solo con filas de `VERSION_MODELO`; si se cambia el motor, subir `VERSION_MODELO` para que la calibración y el sesgo por equipo no aprendan de números de otro motor.
- Importar `liga_mx_algoritmo` desde `liga_mx_supabase` a nivel de módulo falla en silencio (import circular); usar imports diferidos dentro de la función.

- Subir una versión de `liga_mx_algoritmo.py` desfasada de `app.py`/`liga_mx_supabase.py` causó dos `TypeError` seguidos por parámetros faltantes (`cuotas_por_partido`, `sesgo_por_equipo`). Si se editan varios archivos relacionados, subir todos juntos en el mismo commit y verificar con `grep` que el parámetro nuevo esté presente antes de dar el cambio por terminado.
- `MAPA_NOMBRES_ODDS_API` en `liga_mx_cuotas.py` originalmente solo cubría los 7 equipos con acento distinto, y `emparejar_equipo()` fallaba en silencio para los 11 equipos con nombre idéntico (Puebla, Toluca, etc.) porque no había un chequeo de "ya es igual, no traducir". Cualquier función de emparejamiento de nombres externos debe probarse contra la lista completa de 18 equipos, no solo los casos "raros".
- Un `str_replace` mal dirigido dejó `calcular_stats_apuestas()` en `liga_mx_supabase.py` sin su `def` y primera línea. Al editar funciones existentes, releer el archivo completo antes y después del cambio, no solo el fragmento tocado.

## Estado de datos (actualizar aquí conforme avance la temporada)

- Jornadas 1–14: completas (125 partidos con resultado y tarjetas/córners en `DATOS_REALES_LIGAMX`), salvo 1 de la Jornada 7.
- Jornada 7: America vs Tijuana ya jugado (28/10, 1-1). Pendiente Queretaro vs Monterrey (reprogramado al 14/11). `detectar_jornada_actual()` ignora jornadas rezagadas (con pendientes pero con una jornada posterior que ya tiene resultados), así que la J7 no le gana a la jornada en curso; se elige a mano en el selector.
- Jornadas 15–17: calendario cargado, sin resultados todavía.
- Análisis de jornada automático: `liga_mx_analisis_semanal.py` simula (10M por partido) y guarda las apuestas ALTA de una jornada **una sola vez, en cuanto todos sus partidos por jugarse tienen árbitro central** (rezagadas, partido por partido; si la FMF cambia un árbitro, ese partido se vuelve a simular). Antes marca aciertos/fallos/nulas de lo ya jugado y usa la retroalimentación del historial (mercados suspendidos, calibración isotónica, sesgo por equipo), igual que la app. Lo corren `arbitros_fmf.yml` (job `analisis`, tras cada revisión de la FMF) y `analisis_semanal.yml` (lunes 12:00 UTC, cada push a main que toque el skeleton, y a mano con `jornada`/`forzar`). Necesita en Secrets del repo `SUPABASE_URL_LIGAMX`, `SUPABASE_KEY_LIGAMX` y opcionalmente `WEATHER_API_KEY`, `BSD_API_KEY`, `ODDS_API_KEY`; sin Supabase no simula (salvo `--forzar`).
- `ODDS_API_KEY` y `SUPABASE_URL_LIGAMX`/`SUPABASE_KEY_LIGAMX` van en Secrets de Streamlit Cloud, nunca hardcodeados ni pegados en el chat/commits.
