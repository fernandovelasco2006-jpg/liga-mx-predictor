# ─────────────────────────────────────────────────────────────────────────
# liga_mx_analisis_semanal.py — Corre TODA la jornada pendiente de una
# sola vez, sin depender de que alguien abra app.py.
#
# QUÉ HACE (en orden):
#   1. Detecta cuál es la próxima jornada con partidos SIN resultado.
#   2. Simula cada uno de esos partidos (Monte Carlo, misma función que ya
#      usa app.py: simular_partido()).
#   3. Calcula las apuestas sugeridas de cada partido (analizar_apuestas()),
#      respetando los mercados que la auto-calibración ya haya suspendido.
#   4. Guarda TODO en Supabase: predicciones + apuestas de nivel ALTA, con
#      acierto=null (pendiente) — usa guardar_prediccion()/guardar_apuestas(),
#      que ya existen en liga_mx_supabase.py y no duplican si ya corriste
#      esto antes en la semana (upsert por id determinístico).
#   5. Arma y guarda el parlay de la jornada (mejor pata de cada partido).
#   6. Antes de simular, también corre la retroalimentación al revés:
#      revisa si hay partidos YA jugados con apuestas pendientes de
#      evaluar (acierto=null) y las marca correcto/incorrecto contra el
#      resultado real ya cargado en PARTIDOS — para que si corres esto
#      un lunes después de que se jugó la jornada anterior, el historial
#      quede al día antes de generar las apuestas nuevas.
#
# CÓMO SE EJECUTA EN AUTOMÁTICO CADA SEMANA
# Este archivo es un script independiente de Streamlit — no importa
# streamlit ni usa st.cache — así que se puede llamar desde:
#   a) GitHub Actions con un cron (recomendado, gratis): agrega
#      .github/workflows/analisis_semanal.yml con un schedule tipo
#      "0 12 * * 1" (todos los lunes 12:00 UTC) que corra
#      `python liga_mx_analisis_semanal.py`.
#   b) Un cron job normal si tu hosting lo soporta.
#   c) A mano: `python liga_mx_analisis_semanal.py` cuando quieras.
#
# Necesita las mismas variables de entorno que app.py:
#   SUPABASE_URL_LIGAMX, SUPABASE_KEY_LIGAMX (obligatorias para guardar)
#   WEATHER_API_KEY (opcional — sin ella, factor_clima=1.0 para todos)
# ─────────────────────────────────────────────────────────────────────────
import os
import sys
from datetime import datetime, timezone, timedelta

from liga_mx_predictor_skeleton import PARTIDOS, HORARIOS_PARTIDO
from liga_mx_algoritmo import simular_partido, analizar_apuestas, armar_parlay

TZ_MX = timezone(timedelta(hours=-6))
N_SIMS_PARTIDO = 10_000_000

# Mismos pesos fijos que usa app.py (ver PESO_ELO/PESO_ALTITUD/PESO_ARBITRO
# en app.py) — si algún día los cambias ahí, cámbialos aquí también para
# que el análisis semanal y la interfaz nunca queden desincronizados.
PESO_ELO = 1.0
PESO_ALTITUD = 1.0
PESO_ARBITRO = 1.0


def _env(nombre: str):
    return os.environ.get(nombre)


def _log(msg: str):
    print(f"[{datetime.now(TZ_MX).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _proxima_jornada_pendiente() -> int:
    """Jornada más baja que tenga AL MENOS un partido sin resultado."""
    pendientes = [p[2] for p in PARTIDOS if p[4] is None]
    if not pendientes:
        return None
    return min(pendientes)


def _partidos_de_jornada(jornada: int) -> list:
    return [p for p in PARTIDOS if p[2] == jornada]


def _factor_clima_partido(local: str, visit: str, weather_api_key: str):
    """Igual criterio que _factor_clima_cached() en app.py, sin caché de
    Streamlit (este script no corre dentro de Streamlit)."""
    try:
        from liga_mx_clima import obtener_clima_partido, factor_clima as _calc
    except ImportError:
        return 1.0
    if not weather_api_key:
        return 1.0
    fecha_hora = HORARIOS_PARTIDO.get((local, visit))
    if not fecha_hora:
        return 1.0
    clima = obtener_clima_partido(local, fecha_hora, weather_api_key)
    return _calc(clima)


def revisar_resultados_pendientes_via_api(api_football_key: str) -> dict:
    """
    Paso 0 (nuevo): antes de tocar Supabase o simular nada, revisa vía
    API-Football si hay partidos que en PARTIDOS siguen como (None, None)
    pero que en la realidad ya se jugaron. NO escribe nada — arma un
    reporte para que lo revises y lo copies a mano a
    liga_mx_predictor_skeleton.py, exactamente como ya hicimos con la
    Jornada 4. Ver liga_mx_api_football.py para el porqué de no
    auto-escribir.

    Devuelve None si no hay API_FOOTBALL_KEY configurada (el resto del
    script sigue funcionando igual, solo sin este paso extra).
    """
    if not api_football_key:
        return None
    try:
        from liga_mx_api_football import generar_actualizacion_pendiente, imprimir_reporte
    except ImportError:
        _log("Aviso: liga_mx_api_football.py no disponible, se omite este paso")
        return None

    jornada = _proxima_jornada_pendiente()
    if jornada is None:
        return None

    try:
        actualizacion = generar_actualizacion_pendiente(api_football_key, jornada)
    except Exception as e:
        _log(f"Aviso: no se pudo consultar API-Football ({e}) — se sigue sin este paso")
        return None

    partidos_ya_en_skeleton = {(p[0], p[1]) for p in PARTIDOS if p[4] is not None}
    nuevos = [p for p in actualizacion["partidos_terminados"]
              if (p["local"], p["visitante"]) not in partidos_ya_en_skeleton]

    if nuevos:
        _log(f"⚠️ API-Football reporta {len(nuevos)} partido(s) de la Jornada {jornada} "
             f"YA TERMINADOS que no están cargados en PARTIDOS todavía:")
        for p in nuevos:
            _log(f"    {p['local']} {p['gh']}-{p['ga']} {p['visitante']} · árbitro: {p['arbitro']}")
        _log("  -> Revísalos y agrégalos a liga_mx_predictor_skeleton.py antes de "
             "confiar en la próxima simulación (o pide que Claude los cargue).")
    if actualizacion["equipos_no_reconocidos"]:
        _log(f"⚠️ Equipos no reconocidos por el mapa de nombres: {actualizacion['equipos_no_reconocidos']}")

    return actualizacion


def actualizar_aciertos_de_jornadas_pasadas(url: str, key: str):
    """Paso 6 del docstring del módulo: pone al día el historial de
    apuestas/parlays de partidos que YA se jugaron pero cuya apuesta
    sigue con acierto=null en Supabase."""
    from liga_mx_supabase import actualizar_aciertos_pendientes, actualizar_parlays_pendientes
    partidos_jugados = [p for p in PARTIDOS if p[4] is not None]
    if not partidos_jugados:
        return
    n_ap = actualizar_aciertos_pendientes(url, key, partidos_jugados)
    n_pa = actualizar_parlays_pendientes(url, key, partidos_jugados)
    _log(f"Aciertos actualizados: {n_ap} apuestas, {n_pa} parlays")


def analizar_jornada(jornada: int, url: str = None, key: str = None,
                      weather_api_key: str = None, guardar: bool = True) -> dict:
    """
    Simula TODOS los partidos de una jornada de una sola vez y, si
    guardar=True y hay credenciales de Supabase, persiste predicciones +
    apuestas + parlay. Devuelve un resumen para log/depuración — nunca
    lanza excepción por un solo partido: si uno falla, sigue con los
    demás (igual criterio de resiliencia que ya usa app.py con sus
    try/except alrededor de Supabase).
    """
    from liga_mx_supabase import (
        guardar_prediccion, guardar_apuestas, guardar_parlay_diario,
        cargar_historial_apuestas, calcular_mercados_suspendidos,
    )

    mercados_susp = frozenset()
    if url and key:
        try:
            historial = cargar_historial_apuestas(url, key)
            mercados_susp = frozenset(calcular_mercados_suspendidos(historial))
            if mercados_susp:
                _log(f"Mercados suspendidos por auto-calibración: {sorted(mercados_susp)}")
        except Exception as e:
            _log(f"Aviso: no se pudo calcular mercados suspendidos ({e}) — se sigue sin filtro")

    partidos = _partidos_de_jornada(jornada)
    resumen = {"jornada": jornada, "partidos_analizados": 0, "apuestas_guardadas": 0, "errores": []}
    patas_parlay = []

    for local, visit, jrn, estadio, resultado, arbitro in partidos:
        if resultado is not None:
            continue  # ya jugado, no hay nada que predecir
        try:
            fc = _factor_clima_partido(local, visit, weather_api_key)
            r = simular_partido(local, visit, n=N_SIMS_PARTIDO,
                                 peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD,
                                 peso_arbitro=PESO_ARBITRO, factor_clima=fc)
            sugs = analizar_apuestas(local, visit, r, mercados_suspendidos=mercados_susp)
            resumen["partidos_analizados"] += 1
            _log(f"  {local} vs {visit}: {r['prob_home']:.1f}% / {r['prob_draw']:.1f}% / {r['prob_away']:.1f}% "
                 f"· {len([s for s in sugs if s['nivel'] == 'ALTA'])} apuestas ALTA")

            if guardar and url and key:
                guardar_prediccion(url, key, local, visit, jrn, r, resultado_real=None)
                n_guardadas = guardar_apuestas(url, key, local, visit, jrn, sugs, resultado_real=None)
                resumen["apuestas_guardadas"] += n_guardadas

            altas = [s for s in sugs if s["nivel"] == "ALTA"]
            if altas:
                mejor = altas[0]
                patas_parlay.append({
                    "local": local, "visitante": visit, "jornada": jrn,
                    "mercado": mejor["mercado"], "seleccion": mejor["seleccion"].replace("✅ ", ""),
                    "confianza": mejor["confianza"],
                })
        except Exception as e:
            _log(f"  ERROR en {local} vs {visit}: {e}")
            resumen["errores"].append(f"{local} vs {visit}: {e}")

    if guardar and url and key and len(patas_parlay) >= 2:
        prob_combinada = 1.0
        for p in patas_parlay:
            prob_combinada *= p["confianza"] / 100
        fecha_hoy = datetime.now(TZ_MX).strftime("%Y-%m-%d")
        ok = guardar_parlay_diario(url, key, f"jornada{jornada}_{fecha_hoy}", patas_parlay, prob_combinada * 100)
        if ok:
            _log(f"Parlay de jornada guardado: {len(patas_parlay)} patas, {prob_combinada*100:.1f}% combinada")

    resumen["patas_parlay"] = patas_parlay
    return resumen


def main():
    url = _env("SUPABASE_URL_LIGAMX")
    key = _env("SUPABASE_KEY_LIGAMX")
    weather_key = _env("WEATHER_API_KEY")
    api_football_key = _env("API_FOOTBALL_KEY")

    if not (url and key):
        _log("AVISO: SUPABASE_URL_LIGAMX / SUPABASE_KEY_LIGAMX no configuradas — "
             "el análisis correrá pero NO se guardará nada. Configúralas como "
             "variables de entorno o secrets del cron para persistir resultados.")

    # 0. Revisa (sin escribir nada) si hay resultados reales nuevos que
    # falten cargar a mano en PARTIDOS — ver revisar_resultados_pendientes_via_api().
    if api_football_key:
        _log("Paso 0/2 — Revisando resultados nuevos vía API-Football...")
        revisar_resultados_pendientes_via_api(api_football_key)
    else:
        _log("Aviso: API_FOOTBALL_KEY no configurada — se omite la revisión "
             "automática de resultados nuevos (seguirás cargándolos a mano).")

    # 1. Al día con lo que ya se jugó antes de generar predicciones nuevas.
    if url and key:
        _log("Paso 1/2 — Actualizando aciertos de jornadas ya jugadas...")
        actualizar_aciertos_de_jornadas_pasadas(url, key)

    # 2. Analiza la próxima jornada pendiente completa.
    jornada = _proxima_jornada_pendiente()
    if jornada is None:
        _log("No hay jornadas pendientes — temporada regular completa.")
        return

    _log(f"Paso 2/2 — Analizando Jornada {jornada}...")
    resumen = analizar_jornada(jornada, url=url, key=key, weather_api_key=weather_key)

    _log(f"Listo. Partidos analizados: {resumen['partidos_analizados']} · "
         f"Apuestas nuevas guardadas: {resumen['apuestas_guardadas']} · "
         f"Errores: {len(resumen['errores'])}")
    if resumen["errores"]:
        for e in resumen["errores"]:
            _log(f"  - {e}")
        sys.exit(1)  # código de salida distinto de 0 → el cron puede alertar


if __name__ == "__main__":
    main()
