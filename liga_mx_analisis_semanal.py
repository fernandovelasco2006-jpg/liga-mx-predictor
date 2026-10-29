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
# CUÁNDO SE GUARDAN LAS APUESTAS (disparo por árbitros)
# Las apuestas de una jornada se generan UNA sola vez, en cuanto todos
# sus partidos por jugarse tienen árbitro central cargado en PARTIDOS
# (lo llena liga_mx_arbitros_fmf.py desde las designaciones FMF). Así el
# historial se arma con el mismo dato que va a pitar el partido, y no con
# el árbitro por defecto. Reglas:
#   - Solo partidos que no han empezado (según HORARIOS_PARTIDO), para que
#     el historial nunca tenga predicciones hechas con el partido en curso.
#   - Jornadas rezagadas (ej. la J7 reprogramada) se revisan partido por
#     partido: no esperan a que se designe el otro rezagado.
#   - Un partido ya guardado con ese MISMO árbitro no se vuelve a simular;
#     si la FMF cambió el árbitro, se simula de nuevo.
#   - --forzar ignora ambas condiciones (útil para correr a mano).
# Lo llaman el workflow de árbitros (en cuanto sube árbitros nuevos) y el
# análisis de los lunes (que además pone al día aciertos/fallos/nulas).
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
#   ODDS_API_KEY (opcional — sin ella, no se calcula value bet en 1X2)
# ─────────────────────────────────────────────────────────────────────────
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

from liga_mx_predictor_skeleton import PARTIDOS, HORARIOS_PARTIDO
from liga_mx_algoritmo import simular_partido, analizar_apuestas, armar_parlay, detectar_jornada_actual

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


def _ya_empezo(local: str, visit: str, ahora: datetime) -> bool:
    """True si el partido ya arrancó según HORARIOS_PARTIDO (hora del
    centro de México). Sin horario cargado se considera que no."""
    horario = HORARIOS_PARTIDO.get((local, visit))
    if not horario:
        return False
    try:
        inicio = datetime.strptime(horario, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_MX)
    except ValueError:
        return False
    return inicio <= ahora


def partidos_listos_por_arbitro(ahora: datetime = None) -> dict:
    """
    {jornada: [partidos]} con los partidos que ya se pueden analizar:
    sin resultado, sin haber empezado y con árbitro central cargado. Una
    jornada regular solo entra cuando TODOS sus partidos por jugarse
    tienen árbitro; una rezagada (hay jornadas posteriores con
    resultados) entra partido por partido.
    """
    ahora = ahora or datetime.now(TZ_MX)
    jugadas = [p[2] for p in PARTIDOS if p[4] is not None]
    ultima = max(jugadas, default=0)
    por_jornada = {}
    for p in PARTIDOS:
        if p[4] is None and not _ya_empezo(p[0], p[1], ahora):
            por_jornada.setdefault(p[2], []).append(p)

    listos = {}
    for jornada, partidos in sorted(por_jornada.items()):
        if jornada < ultima:
            con_arbitro = [p for p in partidos if p[5]]
        else:
            con_arbitro = partidos if all(p[5] for p in partidos) else []
        if con_arbitro:
            listos[jornada] = con_arbitro
    return listos


def arbitros_ya_guardados(url: str, key: str, jornada: int) -> dict:
    """{(local, visitante): arbitro} de las predicciones ya guardadas en
    Supabase para esa jornada — sirve para no repetir un partido que ya
    se analizó con el mismo árbitro."""
    import requests
    from liga_mx_supabase import _headers
    try:
        resp = requests.get(
            f"{url}/rest/v1/predicciones_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "local,visitante,arbitro", "jornada": f"eq.{jornada}"},
            timeout=10,
        )
        filas = resp.json() if resp.status_code == 200 else []
    except Exception:
        filas = []
    return {(f["local"], f["visitante"]): f.get("arbitro") for f in filas}


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


def revisar_resultados_pendientes_via_api(bsd_api_key: str) -> dict:
    """
    Paso 0: antes de tocar Supabase o simular nada, revisa vía Bzzoiro
    Sports Data (BSD) si hay partidos que en PARTIDOS siguen como
    (None, None) pero que en la realidad ya se jugaron. NO escribe nada
    — arma un reporte para que lo revises y lo copies a mano a
    liga_mx_predictor_skeleton.py, exactamente como ya hicimos con la
    Jornada 4. Ver liga_mx_bsd.py para el porqué de no auto-escribir.

    NOTA: se usa BSD (sports.bzzoiro.com) en vez de API-Football porque
    el plan gratis de API-Football no cubre la temporada 2026 en curso
    (solo tiene histórico 2022-2024) — ver liga_mx_bsd.py para más
    contexto. liga_mx_api_football.py se conserva por si en el futuro
    hace falta consultar esas temporadas históricas.

    Devuelve None si no hay BSD_API_KEY configurada (el resto del
    script sigue funcionando igual, solo sin este paso extra).
    """
    if not bsd_api_key:
        return None
    try:
        from liga_mx_bsd import generar_actualizacion_pendiente, LEAGUE_ID_APERTURA
    except ImportError:
        _log("Aviso: liga_mx_bsd.py no disponible, se omite este paso")
        return None

    jornada = _proxima_jornada_pendiente()
    if jornada is None:
        return None

    try:
        actualizacion = generar_actualizacion_pendiente(bsd_api_key, jornada, LEAGUE_ID_APERTURA)
    except Exception as e:
        _log(f"Aviso: no se pudo consultar BSD ({e}) — se sigue sin este paso")
        return None

    partidos_ya_en_skeleton = {(p[0], p[1]) for p in PARTIDOS if p[4] is not None}
    nuevos = [p for p in actualizacion["partidos_terminados"]
              if (p["local"], p["visitante"]) not in partidos_ya_en_skeleton]

    if nuevos:
        _log(f"⚠️ BSD reporta {len(nuevos)} partido(s) de la Jornada {jornada} "
             f"YA TERMINADOS que no están cargados en PARTIDOS todavía:")
        _log("")
        _log("  — Copia esto a PARTIDOS en liga_mx_predictor_skeleton.py —")
        for p in nuevos:
            estadio_actual = next((pp[3] for pp in PARTIDOS if pp[0] == p["local"] and pp[1] == p["visitante"]), "")
            _log(f"    ('{p['local']}', '{p['visitante']}', {jornada}, '{estadio_actual}', "
                 f"({p['gh']}, {p['ga']}), '{p['arbitro'] or ''}'),")
        _log("")
        _log("  — Copia esto a DATOS_REALES_LIGAMX (si trae am/co/ro) —")
        for p in nuevos:
            campos = {k: p[k] for k in ("am", "co", "ro") if k in p}
            if campos:
                clave = f"{p['local']}_{p['visitante']}"
                _log(f"    \"{clave}\": {campos},")
        _log("")
        _log("  -> Revísalo antes de copiarlo (o pide que Claude lo cargue).")
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


def cargar_retroalimentacion(url: str = None, key: str = None) -> dict:
    """
    Lo que el historial real ya le enseñó al modelo, con las mismas
    funciones que usa app.py (_mercados_suspendidos_cached,
    _tablas_calibracion_cached, _sesgo_equipo_cached), para que lo que se
    guarda aquí sea exactamente lo que la app hubiera recomendado.
    Sin credenciales o si Supabase falla, todo queda vacío (modelo base).
    """
    retro = {"historial": [], "mercados_suspendidos": frozenset(),
             "tablas_calibracion": {}, "sesgo_por_equipo": {}}
    if not (url and key):
        return retro
    from liga_mx_supabase import (
        cargar_historial_apuestas, cargar_historial_predicciones,
        calcular_mercados_suspendidos, calibrar_confianza_por_mercado,
        calcular_sesgo_por_equipo,
    )
    try:
        historial = cargar_historial_apuestas(url, key)
        retro["historial"] = historial
        retro["mercados_suspendidos"] = frozenset(calcular_mercados_suspendidos(historial))
        retro["tablas_calibracion"] = calibrar_confianza_por_mercado(historial)
        retro["sesgo_por_equipo"] = calcular_sesgo_por_equipo(cargar_historial_predicciones(url, key))
    except Exception as e:
        _log(f"Aviso: no se pudo cargar la retroalimentación ({e}) — se sigue con lo que haya")
    if retro["mercados_suspendidos"]:
        _log(f"Mercados suspendidos por auto-calibración: {sorted(retro['mercados_suspendidos'])}")
    if retro["tablas_calibracion"]:
        _log(f"Mercados con confianza recalibrada: {sorted(retro['tablas_calibracion'])}")
    if retro["sesgo_por_equipo"]:
        _log(f"Equipos con corrección de sesgo: {len(retro['sesgo_por_equipo'])}")
    return retro


def _cuotas_por_partido(odds_api_key: str) -> dict:
    """Igual que _cuotas_jornada_cached() en app.py: {(local, visita): partido}."""
    if not odds_api_key:
        return {}
    try:
        from liga_mx_cuotas import obtener_cuotas_jornada
        return {(p["home_team"], p["away_team"]): p for p in obtener_cuotas_jornada(odds_api_key)}
    except Exception as e:
        _log(f"Aviso: no se pudieron traer cuotas ({e}) — se sigue sin value bet")
        return {}


def analizar_jornada(jornada: int, url: str = None, key: str = None,
                      weather_api_key: str = None, guardar: bool = True,
                      partidos: list = None, retro: dict = None,
                      cuotas_por_partido: dict = None) -> dict:
    """
    Simula los partidos pendientes de una jornada (10M iteraciones cada
    uno) y, si guardar=True y hay credenciales de Supabase, persiste
    predicciones + apuestas + parlay. partidos: opcional, solo esos
    partidos (por defecto todos los pendientes de la jornada). retro:
    salida de cargar_retroalimentacion() (se carga aquí si no se pasa).
    Devuelve un resumen para log/depuración — nunca lanza excepción por
    un solo partido: si uno falla, sigue con los demás (igual criterio de
    resiliencia que ya usa app.py con sus try/except alrededor de
    Supabase).
    """
    from liga_mx_supabase import guardar_prediccion, guardar_apuestas, guardar_parlay_diario

    if retro is None:
        retro = cargar_retroalimentacion(url, key)
    cuotas_por_partido = cuotas_por_partido or {}

    if partidos is None:
        partidos = _partidos_de_jornada(jornada)
    resumen = {"jornada": jornada, "partidos_analizados": 0, "apuestas_guardadas": 0,
               "errores": [], "apuestas": []}
    patas_parlay = []

    for local, visit, jrn, estadio, resultado, arbitro in partidos:
        if resultado is not None:
            continue  # ya jugado, no hay nada que predecir
        try:
            fc = _factor_clima_partido(local, visit, weather_api_key)
            r = simular_partido(local, visit, n=N_SIMS_PARTIDO,
                                 peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD,
                                 peso_arbitro=PESO_ARBITRO, factor_clima=fc,
                                 sesgo_por_equipo=retro["sesgo_por_equipo"])
            cuota = cuotas_por_partido.get((local, visit))
            sugs = analizar_apuestas(local, visit, r,
                                      mercados_suspendidos=retro["mercados_suspendidos"],
                                      cuotas=cuota["cuotas"] if cuota else None,
                                      cuotas_totales=cuota["cuotas_totales"] if cuota else None,
                                      tablas_calibracion=retro["tablas_calibracion"])
            altas = [s for s in sugs if s["nivel"] == "ALTA"]
            resumen["partidos_analizados"] += 1
            _log(f"  {local} vs {visit} ({r['arbitro']}): {r['prob_home']:.1f}% / {r['prob_draw']:.1f}% / "
                 f"{r['prob_away']:.1f}% · {len(altas)} apuestas ALTA")
            for s in altas:
                _log(f"      {s['mercado']}: {s['seleccion'].replace('✅ ', '')} ({s['confianza']:.1f}%)")
                resumen["apuestas"].append((local, visit, s["mercado"],
                                            s["seleccion"].replace("✅ ", ""), s["confianza"]))

            if guardar and url and key:
                guardar_prediccion(url, key, local, visit, jrn, r, resultado_real=None)
                n_guardadas = guardar_apuestas(url, key, local, visit, jrn, sugs, resultado_real=None)
                resumen["apuestas_guardadas"] += n_guardadas

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


def reporte_retroalimentacion(historial: list) -> str:
    """
    Resumen en Markdown del historial ya verificado: aciertos, fallos,
    nulas y pendientes por jornada y por mercado. Se imprime en el log y,
    dentro de GitHub Actions, en el resumen de la corrida.
    """
    from liga_mx_supabase import calcular_stats_apuestas, calcular_stats_por_mercado
    if not historial:
        return "Sin apuestas guardadas todavía."

    total = calcular_stats_apuestas(historial)
    lineas = [
        f"**Total:** {total['aciertos']} aciertos · {total['fallos']} fallos · "
        f"{total['total_nulas']} nulas · {total['total_pendientes']} pendientes · "
        f"acierto {total['accuracy']:.1f}%",
        "",
        "| Jornada | Aciertos | Fallos | Nulas | Pendientes | Acierto |",
        "|---|---|---|---|---|---|",
    ]
    por_jornada = {}
    for a in historial:
        por_jornada.setdefault(a.get("jornada"), []).append(a)
    for jornada in sorted(por_jornada, key=lambda j: (j is None, j), reverse=True):
        st = calcular_stats_apuestas(por_jornada[jornada])
        pct = f"{st['accuracy']:.0f}%" if st["total_evaluadas"] else "—"
        lineas.append(f"| {jornada} | {st['aciertos']} | {st['fallos']} | {st['total_nulas']} | "
                      f"{st['total_pendientes']} | {pct} |")

    mercados = calcular_stats_por_mercado(historial, minimo_evaluadas=1)
    if mercados:
        lineas += ["", "| Mercado | Evaluadas | Acierto real | Confianza prom. | Diagnóstico |",
                   "|---|---|---|---|---|"]
        for m in mercados:
            lineas.append(f"| {m['mercado']} | {m['n_evaluadas']} | {m['accuracy_real']}% | "
                          f"{m['confianza_promedio']}% | {m['diagnostico']} |")
    return "\n".join(lineas)


def _escribir_resumen_actions(texto: str):
    ruta = _env("GITHUB_STEP_SUMMARY")
    if not ruta:
        return
    try:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(texto + "\n\n")
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description="Análisis de jornada Liga MX (simulación + apuestas en Supabase)")
    ap.add_argument("--jornada", type=int, help="analizar solo esta jornada")
    ap.add_argument("--forzar", action="store_true",
                    help="analizar aunque falten árbitros o ya se haya guardado con el mismo árbitro")
    ap.add_argument("--solo-verificar", action="store_true",
                    help="solo marcar aciertos/fallos/nulas, sin simular")
    args = ap.parse_args()

    url = _env("SUPABASE_URL_LIGAMX")
    key = _env("SUPABASE_KEY_LIGAMX")
    weather_key = _env("WEATHER_API_KEY")
    bsd_api_key = _env("BSD_API_KEY")
    odds_api_key = _env("ODDS_API_KEY")

    if not (url and key):
        _log("AVISO: SUPABASE_URL_LIGAMX / SUPABASE_KEY_LIGAMX no configuradas — "
             "el análisis correrá pero NO se guardará nada. Configúralas como "
             "variables de entorno o secrets del cron para persistir resultados.")

    # 0. Revisa (sin escribir nada) si hay resultados reales nuevos que
    # falten cargar a mano en PARTIDOS — ver revisar_resultados_pendientes_via_api().
    if bsd_api_key:
        _log("Paso 0/3 — Revisando resultados nuevos vía BSD...")
        revisar_resultados_pendientes_via_api(bsd_api_key)

    # 1. Al día con lo que ya se jugó antes de generar predicciones nuevas.
    if url and key:
        _log("Paso 1/3 — Verificando apuestas de partidos ya jugados...")
        actualizar_aciertos_de_jornadas_pasadas(url, key)

    # 2. Retroalimentación: lo que el historial ya verificado corrige.
    _log("Paso 2/3 — Cargando retroalimentación del historial...")
    retro = cargar_retroalimentacion(url, key)
    if retro["historial"]:
        reporte = reporte_retroalimentacion(retro["historial"])
        _log("Historial de apuestas:\n" + reporte)
        _escribir_resumen_actions("## Historial de apuestas verificadas\n\n" + reporte)

    if args.solo_verificar:
        return

    # 3. Qué partidos ya se pueden analizar. Sin Supabase no hay dónde
    # guardar ni cómo saber si ya se analizó: solo se simula con --forzar.
    if not (url and key) and not args.forzar:
        _log("Paso 3/3 — Sin credenciales de Supabase: no se simula (usa --forzar para probar).")
        return
    if args.forzar:
        jornada = args.jornada or detectar_jornada_actual()
        if jornada is None:
            _log("No hay jornadas pendientes — temporada regular completa.")
            return
        listos = {jornada: [p for p in _partidos_de_jornada(jornada) if p[4] is None]}
    else:
        listos = partidos_listos_por_arbitro()
        if args.jornada:
            listos = {j: ps for j, ps in listos.items() if j == args.jornada}
        for jornada in list(listos):
            guardados = arbitros_ya_guardados(url, key, jornada)
            faltan = [p for p in listos[jornada] if guardados.get((p[0], p[1])) != p[5]]
            if faltan:
                listos[jornada] = faltan
            else:
                _log(f"Jornada {jornada}: ya guardada con estos árbitros, no se repite.")
                del listos[jornada]

    if not listos:
        _log("Paso 3/3 — Ninguna jornada lista: faltan árbitros centrales o ya se analizó.")
        return

    cuotas = _cuotas_por_partido(odds_api_key)
    errores = []
    resumen_md = []
    for jornada, partidos in listos.items():
        _log(f"Paso 3/3 — Analizando Jornada {jornada} ({len(partidos)} partidos, "
             f"{N_SIMS_PARTIDO:,} simulaciones cada uno)...")
        resumen = analizar_jornada(jornada, url=url, key=key, weather_api_key=weather_key,
                                    partidos=partidos, retro=retro, cuotas_por_partido=cuotas)
        _log(f"Listo J{jornada}. Partidos analizados: {resumen['partidos_analizados']} · "
             f"Apuestas guardadas: {resumen['apuestas_guardadas']} · "
             f"Errores: {len(resumen['errores'])}")
        errores += resumen["errores"]
        resumen_md += [f"## Apuestas recomendadas · Jornada {jornada}", "",
                       "| Partido | Mercado | Selección | Confianza |", "|---|---|---|---|"]
        resumen_md += [f"| {l} vs {v} | {m} | {s} | {c:.1f}% |" for l, v, m, s, c in resumen["apuestas"]]
        resumen_md.append("")
    _escribir_resumen_actions("\n".join(resumen_md))

    if errores:
        for e in errores:
            _log(f"  - {e}")
        sys.exit(1)  # código de salida distinto de 0 → el cron puede alertar


if __name__ == "__main__":
    main()
