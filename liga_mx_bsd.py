# ─────────────────────────────────────────────────────────────────────────
# liga_mx_bsd.py — Integración con Bzzoiro Sports Data (BSD,
# sports.bzzoiro.com) para traer AUTOMÁTICAMENTE resultados, árbitros,
# tarjetas y córners de cada jornada jugada de Liga MX.
#
# POR QUÉ ESTE PROVEEDOR Y NO API-FOOTBALL
# El plan gratis de API-Football solo cubre 3 temporadas históricas
# (a la fecha de escribir esto: 2022-2024) — NO incluye la temporada
# 2026 en curso, así que era inservible para este proyecto. BSD es
# gratis, sin límite de requests, y cubre la temporada actual completa,
# incluyendo Liga MX Apertura (id 19) y Clausura (id 20) como ligas
# separadas — más limpio que API-Football, que las mezcla en una sola
# "Liga MX" con "rounds".
#
# Ver liga_mx_api_football.py (código anterior, aún funcional para otras
# temporadas si algún día hace falta consultar 2022-2024) — este módulo
# lo reemplaza como fuente principal para la temporada en curso.
#
# CÓMO CONSEGUIR LA API KEY (gratis, sin límite documentado de requests,
# sin tarjeta):
#   1. Regístrate en https://sports.bzzoiro.com/register/
#   2. Ve a tu cuenta y copia el API key.
#   3. Guárdala como variable de entorno BSD_API_KEY (o en st.secrets si
#      usas Streamlit) — igual patrón que las demás keys del proyecto.
#
# LEAGUE_ID YA CONFIRMADO (verificado en sports.bzzoiro.com/leagues/,
# agosto 2026):
#   19 = Liga MX Apertura
#   20 = Liga MX Clausura
#
# QUÉ TRAE:
#   - obtener_resultados_jornada(): resultados + árbitro + venue de cada
#     partido de una jornada (round_number).
#   - obtener_tarjetas_corners_partido(): tarjetas amarillas/rojas y
#     córners de un partido específico vía /incidents/ (para llenar
#     DATOS_REALES_LIGAMX).
#
# QUÉ NO HACE (a propósito, mismo principio que liga_mx_api_football.py):
#   Este módulo NUNCA escribe directo en liga_mx_predictor_skeleton.py.
#   Devuelve los datos en un formato fácil de revisar — la escritura al
#   archivo la hace un paso separado y explícito.
# ─────────────────────────────────────────────────────────────────────────
import os
import sys
import time
import requests

API_BASE = "https://sports.bzzoiro.com/api/v2"

LEAGUE_ID_APERTURA = 19
LEAGUE_ID_CLAUSURA = 20

# ─────────────────────────────────────────────────────────────────────────
# MAPA DE NOMBRES — BSD puede usar nombres distintos a los que ya
# tenemos en EQUIPOS (liga_mx_predictor_skeleton.py). Igual criterio que
# en liga_mx_api_football.py: traducir explícitamente, avisar si un
# nombre no se reconoce, nunca adivinar en silencio.
# ─────────────────────────────────────────────────────────────────────────
MAPA_NOMBRES_BSD_A_PROYECTO = {
    "America": "America", "Club America": "America", "Club América": "America",
    "Atlante": "Atlante", "Atlante FC": "Atlante",
    "Atlas": "Atlas", "Atlas FC": "Atlas",
    "Atletico San Luis": "Atletico San Luis", "Atlético San Luis": "Atletico San Luis",
    "San Luis": "Atletico San Luis",
    "Cruz Azul": "Cruz Azul",
    "Guadalajara": "Guadalajara", "Chivas Guadalajara": "Guadalajara", "Chivas": "Guadalajara",
    "CD Guadalajara": "Guadalajara",
    "Juarez": "FC Juarez", "FC Juarez": "FC Juarez", "FC Juárez": "FC Juarez", "Club Juarez": "FC Juarez",
    "Leon": "Leon", "León": "Leon", "Club Leon": "Leon", "Club León": "Leon",
    "Monterrey": "Monterrey", "CF Monterrey": "Monterrey", "Rayados": "Monterrey",
    "Necaxa": "Necaxa", "Club Necaxa": "Necaxa",
    "Pachuca": "Pachuca", "CF Pachuca": "Pachuca",
    "Puebla": "Puebla", "Club Puebla": "Puebla",
    "Pumas UNAM": "Pumas UNAM", "Pumas": "Pumas UNAM", "UNAM": "Pumas UNAM",
    "Queretaro": "Queretaro", "Querétaro": "Queretaro", "Querétaro FC": "Queretaro",
    "Santos Laguna": "Santos Laguna", "Santos": "Santos Laguna",
    "Tijuana": "Tijuana", "Club Tijuana": "Tijuana", "Xolos": "Tijuana",
    "Tigres": "Tigres", "Tigres UANL": "Tigres",
    "Toluca": "Toluca", "Deportivo Toluca": "Toluca", "CD Toluca": "Toluca",
}

# Mazatlán FC es el nombre histórico con el que BSD todavía identifica
# la franquicia que ahora juega como Atlante (reubicación de club, no
# equipo nuevo) — mismo criterio que ya usa liga_mx_predictor_skeleton.py
# al heredar datos de Mazatlán para Atlante mientras no hay suficiente
# historial propio.
MAPA_NOMBRES_BSD_A_PROYECTO["Mazatlán FC"] = "Atlante"
MAPA_NOMBRES_BSD_A_PROYECTO["Mazatlan FC"] = "Atlante"


def _traducir_nombre_equipo(nombre_bsd: str) -> str:
    """Igual criterio que en liga_mx_api_football.py: si no reconoce el
    nombre, lo deja tal cual y avisa por stderr — nunca cruza en
    silencio con el equipo equivocado."""
    if nombre_bsd in MAPA_NOMBRES_BSD_A_PROYECTO:
        return MAPA_NOMBRES_BSD_A_PROYECTO[nombre_bsd]
    print(f"AVISO: equipo '{nombre_bsd}' no está en MAPA_NOMBRES_BSD_A_PROYECTO — "
          f"agrégalo antes de confiar en este dato.", file=sys.stderr)
    return nombre_bsd


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Token {api_key}"}


def _get(endpoint: str, api_key: str, params: dict = None, reintentos: int = 2) -> dict:
    """GET con reintento simple ante 429 (rate limit)."""
    url = f"{API_BASE}/{endpoint.lstrip('/')}"
    for intento in range(reintentos + 1):
        try:
            resp = requests.get(url, headers=_headers(api_key), params=params or {}, timeout=10)
            if resp.status_code == 429 and intento < reintentos:
                time.sleep(2)
                continue
            if resp.status_code == 401:
                print("ERROR: API key inválida o faltante (401)", file=sys.stderr)
                return {}
            if resp.status_code == 402:
                print("ERROR: este endpoint requiere un plan de pago (402)", file=sys.stderr)
                return {}
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if intento < reintentos:
                time.sleep(2)
                continue
            print(f"ERROR llamando {endpoint}: {e}", file=sys.stderr)
            return {}
    return {}


_CACHE_ARBITROS = {}  # referee_id -> nombre, para no repetir llamadas en la misma corrida


def _resolver_nombre_arbitro(api_key: str, referee_id) -> str:
    """referee_id viene como número en /events/, no el nombre — hay que
    resolverlo aparte en /referees/{id}/. Se cachea en memoria durante
    la corrida del script para no gastar requests de más si varios
    partidos de la misma jornada comparten árbitro."""
    if referee_id is None:
        return None
    if referee_id in _CACHE_ARBITROS:
        return _CACHE_ARBITROS[referee_id]
    data = _get(f"referees/{referee_id}/", api_key)
    nombre = data.get("name") if isinstance(data, dict) else None
    _CACHE_ARBITROS[referee_id] = nombre
    return nombre


def obtener_resultados_jornada(api_key: str, jornada: int,
                                league_id: int = LEAGUE_ID_APERTURA,
                                resolver_arbitros: bool = True,
                                dias_ventana: int = 21) -> list:
    """
    Trae todos los partidos de una jornada (round_number). Devuelve una
    lista de dicts:
      {event_id, local, visitante, gh, ga, arbitro, estado, fecha}

    ESQUEMA REAL CONFIRMADO (agosto 2026, verificado contra la API en
    vivo — la documentación pública no coincidía en varios campos):
      - home_team / away_team llegan como STRING con el nombre del
        equipo, NO como objeto {"name": ...}.
      - referee_id es un ID numérico; el nombre del árbitro requiere una
        llamada aparte a /referees/{id}/ (resolver_arbitros=True la hace
        automático, con caché en memoria para no repetir).
      - status observado en partidos futuros: "notstarted". El valor
        para partidos terminados aún no se ha confirmado contra un
        response real — generar_actualizacion_pendiente() usa
        home_score/away_score no nulos como señal de que ya terminó,
        más robusto que depender de un string exacto de status.
      - round_number SÍ viene en la respuesta, pero no está confirmado
        como parámetro de filtro aceptado por el endpoint — por eso se
        filtra en Python, no vía query param.
      - date_from/date_to SÍ son parámetros de filtro confirmados
        (documentación oficial de BSD, formato YYYY-MM-DD) — se usan
        para acotar la búsqueda a una ventana de fechas alrededor de
        HOY en vez de recorrer TODA la historia de la liga (miles de
        partidos), que es lo que causaba que el script se colgara.
        dias_ventana controla cuántos días hacia atrás y adelante se
        buscan — 21 cubre de sobra una jornada reciente o próxima sin
        traer partidos de temporadas pasadas.
    """
    from datetime import date, timedelta
    hoy = date.today()
    date_from = (hoy - timedelta(days=dias_ventana)).isoformat()
    date_to = (hoy + timedelta(days=dias_ventana)).isoformat()

    resultados = []
    params = {"league_id": league_id, "limit": 100, "date_from": date_from, "date_to": date_to}
    offset = 0
    max_paginas = 5  # con la ventana de fechas acotada, esto es más que suficiente

    for _ in range(max_paginas):
        data = _get("events/", api_key, {**params, "offset": offset})
        items = data.get("results", []) if isinstance(data, dict) else []
        if not items:
            break

        for item in items:
            if item.get("round_number") != jornada:
                continue
            local_raw = item.get("home_team")
            visit_raw = item.get("away_team")
            # Defensivo: si algún día la API cambia a objeto, seguimos
            # funcionando en vez de tronar.
            local_nombre = local_raw.get("name") if isinstance(local_raw, dict) else local_raw
            visit_nombre = visit_raw.get("name") if isinstance(visit_raw, dict) else visit_raw

            arbitro = None
            if resolver_arbitros and item.get("referee_id"):
                arbitro = _resolver_nombre_arbitro(api_key, item.get("referee_id"))

            resultados.append({
                "event_id": item.get("id"),
                "local": _traducir_nombre_equipo(local_nombre or ""),
                "visitante": _traducir_nombre_equipo(visit_nombre or ""),
                "gh": item.get("home_score"),
                "ga": item.get("away_score"),
                "arbitro": arbitro,
                "estado": item.get("status"),
                "fecha": item.get("event_date"),
            })

        if not data.get("next"):
            break
        offset += 100

    return resultados


def obtener_tarjetas_corners_partido(api_key: str, event_id: int) -> dict:
    """
    Trae tarjetas amarillas/rojas de un partido vía /incidents/.

    ESQUEMA REAL CONFIRMADO (agosto 2026, verificado contra la API en
    vivo con un partido real — Atlante vs Toluca, event_id 211525):
      - La respuesta NO trae {"results": [...]}, es directo
        {"event_id": ..., "incidents": [...]}.
      - Cada tarjeta tiene "type": "card" (no "yellow_card"/"red_card"
        como se asumía antes) — el color va en un campo separado:
        "card_type": "yellow" | "red".
      - No se ha visto todavía un ejemplo con tarjeta anulada por VAR,
        así que el campo exacto para eso (si existe) sigue sin
        confirmar — se revisa best-effort por si aparece como
        "rescinded" o "cancelled", pero no bloquea el conteo si no está.

    Los córners no vienen en /incidents/; se intentan vía /stats/ como
    antes (ya confirmado funcionando: co=11, co=12, etc. en la prueba
    real de la Jornada 4).

    Devuelve {"am": total, "ro": total, "co": total} — solo con las
    claves que sí se pudieron determinar, igual patrón que
    DATOS_REALES_LIGAMX cuando falta un dato.
    """
    resultado = {}

    incidentes = _get(f"events/{event_id}/incidents/", api_key)
    lista = incidentes.get("incidents") if isinstance(incidentes, dict) else None
    if isinstance(lista, list):
        am, ro = 0, 0
        for ev in lista:
            if not isinstance(ev, dict):
                continue
            # Best-effort: si algún día aparece un campo de anulación
            # (VAR revierte la tarjeta), no la contamos. No confirmado
            # aún contra un ejemplo real — se revisan ambos nombres
            # plausibles por seguridad.
            if ev.get("rescinded") or ev.get("cancelled"):
                continue
            if ev.get("type") != "card":
                continue
            card_type = (ev.get("card_type") or "").lower()
            if card_type == "yellow":
                am += 1
            elif card_type == "red":
                ro += 1
            elif card_type in ("second_yellow", "yellow_red"):
                am += 1
                ro += 1
        resultado["am"] = am
        resultado["ro"] = ro

    stats = _get(f"events/{event_id}/stats/", api_key)
    if stats and "stats" in stats:
        home_co = stats["stats"].get("home", {}).get("corner_kicks")
        away_co = stats["stats"].get("away", {}).get("corner_kicks")
        if home_co is not None and away_co is not None:
            resultado["co"] = home_co + away_co

    return resultado


def generar_actualizacion_pendiente(api_key: str, jornada: int, league_id: int = LEAGUE_ID_APERTURA,
                                     incluir_estadisticas: bool = True) -> dict:
    """
    Igual función que en liga_mx_api_football.py: junta resultados +
    estadísticas de los partidos ya finalizados de una jornada, en un
    dict pensado para REVISAR antes de escribir a mano en
    liga_mx_predictor_skeleton.py.
    """
    resultados = obtener_resultados_jornada(api_key, jornada, league_id)
    terminados, sin_terminar, no_reconocidos = [], [], []

    for r in resultados:
        if r["local"] not in MAPA_NOMBRES_BSD_A_PROYECTO.values():
            no_reconocidos.append(r["local"])
        if r["visitante"] not in MAPA_NOMBRES_BSD_A_PROYECTO.values():
            no_reconocidos.append(r["visitante"])

        # Señal de "ya terminó": status == "finished" — confirmado
        # contra un response real (Atlante vs Toluca, event_id 211525,
        # agosto 2026). Se exige también marcador no nulo como
        # verificación extra: dos señales coincidiendo dan más
        # confianza que una sola.
        if r["estado"] == "finished" and r["gh"] is not None and r["ga"] is not None:
            fila = dict(r)
            if incluir_estadisticas and r["event_id"]:
                stats = obtener_tarjetas_corners_partido(api_key, r["event_id"])
                fila.update(stats)
            terminados.append(fila)
        else:
            sin_terminar.append(r)

    return {
        "jornada": jornada,
        "partidos_terminados": terminados,
        "partidos_sin_terminar": sin_terminar,
        "equipos_no_reconocidos": sorted(set(no_reconocidos)),
    }


def imprimir_reporte(actualizacion: dict):
    """Mismo formato que liga_mx_api_football.imprimir_reporte(), para
    que el flujo de revisión manual sea idéntico sin importar cuál de
    los dos módulos se use."""
    j = actualizacion["jornada"]
    print(f"\n── Jornada {j} — partidos con marcador (revisa 'estado' la primera vez) ──")
    for p in actualizacion["partidos_terminados"]:
        stats = []
        if "am" in p:
            stats.append(f"am={p['am']}")
        if "co" in p:
            stats.append(f"co={p['co']}")
        if "ro" in p:
            stats.append(f"ro={p['ro']}")
        stats_str = f" [{', '.join(stats)}]" if stats else ""
        print(f"  {p['local']} {p['gh']}-{p['ga']} {p['visitante']} "
              f"· árbitro: {p['arbitro'] or 'sin dato'} · estado: {p['estado']}{stats_str}")

    if actualizacion["partidos_sin_terminar"]:
        print(f"\n  Sin terminar todavía ({len(actualizacion['partidos_sin_terminar'])}):")
        for p in actualizacion["partidos_sin_terminar"]:
            print(f"    {p['local']} vs {p['visitante']} — estado: {p['estado']}")

    if actualizacion["equipos_no_reconocidos"]:
        print(f"\n  ⚠️ EQUIPOS NO RECONOCIDOS (revisar MAPA_NOMBRES_BSD_A_PROYECTO): "
              f"{actualizacion['equipos_no_reconocidos']}")


if __name__ == "__main__":
    api_key = os.environ.get("BSD_API_KEY")
    if not api_key:
        print("Configura la variable de entorno BSD_API_KEY primero.")
        sys.exit(1)

    jornada = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    actualizacion = generar_actualizacion_pendiente(api_key, jornada)
    imprimir_reporte(actualizacion)
