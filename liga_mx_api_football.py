# ─────────────────────────────────────────────────────────────────────────
# liga_mx_api_football.py — Integración con API-Football (api-football.com
# / api-sports.io) para traer AUTOMÁTICAMENTE resultados, árbitros,
# tarjetas y córners de cada jornada jugada de Liga MX, en vez de
# copiarlos a mano cada semana.
#
# CÓMO CONSEGUIR LA API KEY (gratis, 100 requests/día, sin tarjeta):
#   1. Regístrate en https://dashboard.api-football.com/register
#   2. Copia tu API key del dashboard.
#   3. Guárdala como variable de entorno API_FOOTBALL_KEY (o en
#      st.secrets si usas Streamlit) — igual patrón que SUPABASE_KEY_LIGAMX.
#
# CÓMO OBTENER EL LEAGUE_ID DE LIGA MX (una sola vez, a mano):
#   Corre esto con tu API key ya configurada:
#     python liga_mx_api_football.py --buscar-liga
#   Te imprime el id correcto (a la fecha de escribir esto, suele ser 262
#   para "Liga MX" — pero SIEMPRE verifica con tu propia key, el id no
#   está documentado públicamente de forma estable) y lo puedes fijar
#   abajo en LEAGUE_ID_LIGA_MX.
#
# QUÉ TRAE:
#   - obtener_resultados_jornada(): resultados + árbitro de cada partido
#     de una jornada ya jugada.
#   - obtener_estadisticas_partido(): tarjetas amarillas/rojas y córners
#     de un partido específico (para llenar DATOS_REALES_LIGAMX).
#
# QUÉ NO HACE (a propósito):
#   Este módulo NUNCA escribe directo en liga_mx_predictor_skeleton.py.
#   Devuelve los datos en un formato fácil de revisar (lista de dicts) —
#   la escritura al archivo la hace un paso separado y explícito, para
#   que siempre haya oportunidad de revisar antes de confiar en un dato
#   externo (ver generar_actualizacion_pendiente() más abajo).
# ─────────────────────────────────────────────────────────────────────────
import os
import sys
import time
import requests

API_BASE = "https://v3.football.api-sports.io"

# ⚠️ Verifica este id con --buscar-liga antes de usarlo en producción —
# ver instrucciones arriba. Puesto aquí como mejor valor conocido, no
# como dato confirmado por una fuente primaria.
LEAGUE_ID_LIGA_MX = 262
TEMPORADA_API = 2026  # API-Football identifica la temporada por el año de inicio

# ─────────────────────────────────────────────────────────────────────────
# MAPA DE NOMBRES — API-Football casi nunca usa el mismo nombre corto
# que ya usamos en EQUIPOS (liga_mx_predictor_skeleton.py). Este mapa
# traduce "como lo devuelve la API" -> "como lo tenemos nosotros".
# IMPORTANTE: confirma estos nombres la primera vez que corras el
# módulo — imprime un aviso si encuentra un equipo que no reconoce, en
# vez de adivinar o descartarlo en silencio.
# ─────────────────────────────────────────────────────────────────────────
MAPA_NOMBRES_API_A_PROYECTO = {
    "America": "America",
    "Club America": "America",
    "Atlante": "Atlante",
    "Atlas": "Atlas",
    "Atlas UANL": "Atlas",
    "Atletico San Luis": "Atletico San Luis",
    "Atlético San Luis": "Atletico San Luis",
    "San Luis": "Atletico San Luis",
    "Cruz Azul": "Cruz Azul",
    "Guadalajara": "Guadalajara",
    "Chivas Guadalajara": "Guadalajara",
    "Chivas": "Guadalajara",
    "Juarez": "FC Juarez",
    "FC Juarez": "FC Juarez",
    "FC Juárez": "FC Juarez",
    "Club Juarez": "FC Juarez",
    "Leon": "Leon",
    "León": "Leon",
    "Club Leon": "Leon",
    "Monterrey": "Monterrey",
    "CF Monterrey": "Monterrey",
    "Rayados": "Monterrey",
    "Necaxa": "Necaxa",
    "Club Necaxa": "Necaxa",
    "Pachuca": "Pachuca",
    "CF Pachuca": "Pachuca",
    "Puebla": "Puebla",
    "Club Puebla": "Puebla",
    "Pumas UNAM": "Pumas UNAM",
    "UNAM": "Pumas UNAM",
    "Pumas": "Pumas UNAM",
    "Queretaro": "Queretaro",
    "Querétaro": "Queretaro",
    "Santos Laguna": "Santos Laguna",
    "Santos": "Santos Laguna",
    "Tijuana": "Tijuana",
    "Club Tijuana": "Tijuana",
    "Xolos": "Tijuana",
    "Tigres": "Tigres",
    "Tigres UANL": "Tigres",
    "Toluca": "Toluca",
    "Deportivo Toluca": "Toluca",
}


def _traducir_nombre_equipo(nombre_api: str) -> str:
    """Traduce un nombre de equipo tal como lo devuelve la API al nombre
    corto que usa el proyecto (EQUIPOS en liga_mx_predictor_skeleton.py).
    Si no lo reconoce, devuelve el nombre original SIN modificar y avisa
    por stderr — mejor un dato visible y raro que un cruce silencioso
    con el equipo equivocado."""
    if nombre_api in MAPA_NOMBRES_API_A_PROYECTO:
        return MAPA_NOMBRES_API_A_PROYECTO[nombre_api]
    print(f"AVISO: equipo '{nombre_api}' no está en MAPA_NOMBRES_API_A_PROYECTO — "
          f"agrégalo antes de confiar en este dato.", file=sys.stderr)
    return nombre_api


def _headers(api_key: str) -> dict:
    return {"x-apisports-key": api_key}


def _get(endpoint: str, api_key: str, params: dict, reintentos: int = 2) -> dict:
    """GET con reintento simple — la API a veces responde 429 (límite por
    minuto, no el diario) si se llama muy rápido en ráfaga."""
    url = f"{API_BASE}/{endpoint}"
    for intento in range(reintentos + 1):
        try:
            resp = requests.get(url, headers=_headers(api_key), params=params, timeout=10)
            if resp.status_code == 429 and intento < reintentos:
                time.sleep(2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if data.get("errors"):
                print(f"AVISO: API-Football devolvió errores: {data['errors']}", file=sys.stderr)
            return data
        except requests.RequestException as e:
            if intento < reintentos:
                time.sleep(2)
                continue
            print(f"ERROR llamando {endpoint}: {e}", file=sys.stderr)
            return {"response": []}
    return {"response": []}


def buscar_league_id(api_key: str) -> list:
    """Utilidad de una sola vez: busca "Liga MX" / "Mexico" en /leagues y
    muestra los ids candidatos, para confirmar LEAGUE_ID_LIGA_MX a mano."""
    data = _get("leagues", api_key, {"country": "Mexico"})
    candidatos = []
    for item in data.get("response", []):
        liga = item.get("league", {})
        pais = item.get("country", {})
        if "liga mx" in liga.get("name", "").lower() or liga.get("type") == "League":
            candidatos.append({
                "id": liga.get("id"), "nombre": liga.get("name"),
                "pais": pais.get("name"), "temporadas": [s.get("year") for s in item.get("seasons", [])],
            })
    return candidatos


def obtener_resultados_jornada(api_key: str, jornada: int, league_id: int = LEAGUE_ID_LIGA_MX,
                                temporada: int = TEMPORADA_API) -> list:
    """
    Trae resultados + árbitro de TODOS los partidos de una jornada
    ("round" en la API). Devuelve una lista de dicts:
      {local, visitante, gh, ga, arbitro, estado, fixture_id}
    estado: "Match Finished" si ya terminó; otro texto si no ha jugado o
    está en curso — así el paso siguiente puede filtrar solo lo que ya
    es un resultado definitivo.

    NOTA sobre "round": API-Football numera las jornadas como
    "Regular Season - N". Si tu liga usa un formato de nombre distinto,
    ajusta `round_nombre` abajo (puedes verlo llamando a
    /fixtures/rounds?league=...&season=...).
    """
    round_nombre = f"Regular Season - {jornada}"
    data = _get("fixtures", api_key, {
        "league": league_id, "season": temporada, "round": round_nombre,
    })

    resultados = []
    for item in data.get("response", []):
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        local_api = teams.get("home", {}).get("name", "")
        visit_api = teams.get("away", {}).get("name", "")
        resultados.append({
            "fixture_id": fixture.get("id"),
            "local": _traducir_nombre_equipo(local_api),
            "visitante": _traducir_nombre_equipo(visit_api),
            "gh": goals.get("home"),
            "ga": goals.get("away"),
            "arbitro": fixture.get("referee"),
            "estado": fixture.get("status", {}).get("long"),
            "fecha": fixture.get("date"),
        })
    return resultados


def obtener_estadisticas_partido(api_key: str, fixture_id: int) -> dict:
    """
    Trae tarjetas amarillas/rojas y córners de un partido específico,
    desglosado por equipo (local/visitante) y sumado — formato listo
    para poblar DATOS_REALES_LIGAMX: {"am": total, "co": total, "ro": total}.
    Si la API no tiene esa estadística para el partido (pasa con
    partidos muy recientes, el detalle a veces tarda unas horas en
    aparecer), el campo faltante se omite del dict, igual que ya hace
    DATOS_REALES_LIGAMX a mano cuando falta un dato.
    """
    data = _get("fixtures/statistics", api_key, {"fixture": fixture_id})
    total_am, total_co, total_ro = 0, 0, 0
    encontrado_am, encontrado_co, encontrado_ro = False, False, False

    for equipo_stats in data.get("response", []):
        for stat in equipo_stats.get("statistics", []):
            tipo = (stat.get("type") or "").lower()
            valor = stat.get("value")
            if valor is None:
                continue
            if tipo == "yellow cards":
                total_am += int(valor)
                encontrado_am = True
            elif tipo == "red cards":
                total_ro += int(valor)
                encontrado_ro = True
            elif tipo == "corner kicks":
                total_co += int(valor)
                encontrado_co = True

    resultado = {}
    if encontrado_am:
        resultado["am"] = total_am
    if encontrado_co:
        resultado["co"] = total_co
    if encontrado_ro:
        resultado["ro"] = total_ro
    return resultado


def generar_actualizacion_pendiente(api_key: str, jornada: int, league_id: int = LEAGUE_ID_LIGA_MX,
                                     temporada: int = TEMPORADA_API, incluir_estadisticas: bool = True) -> dict:
    """
    Junta resultados_jornada() + estadísticas_partido() de los partidos
    ya finalizados de una jornada, en un solo dict pensado para REVISAR
    antes de escribir a mano en liga_mx_predictor_skeleton.py — nunca
    escribe el archivo directo (ver el docstring del módulo, arriba).

    Devuelve:
      {
        "jornada": N,
        "partidos_terminados": [
          {"local", "visitante", "gh", "ga", "arbitro", "am", "co", "ro"}, ...
        ],
        "partidos_sin_terminar": [...],  # mismo formato, sin gh/ga confiables
        "equipos_no_reconocidos": [...],  # alerta si el mapa de nombres falló
      }
    """
    resultados = obtener_resultados_jornada(api_key, jornada, league_id, temporada)
    terminados, sin_terminar, no_reconocidos = [], [], []

    for r in resultados:
        if r["local"] not in MAPA_NOMBRES_API_A_PROYECTO.values():
            no_reconocidos.append(r["local"])
        if r["visitante"] not in MAPA_NOMBRES_API_A_PROYECTO.values():
            no_reconocidos.append(r["visitante"])

        if r["estado"] == "Match Finished" and r["gh"] is not None:
            fila = dict(r)
            if incluir_estadisticas and r["fixture_id"]:
                stats = obtener_estadisticas_partido(api_key, r["fixture_id"])
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
    """Imprime la actualización en un formato fácil de comparar a mano
    contra liga_mx_predictor_skeleton.py antes de copiarla — mismo
    espíritu que el proceso manual que ya usamos para la Jornada 4."""
    j = actualizacion["jornada"]
    print(f"\n── Jornada {j} — partidos terminados ──")
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
              f"· árbitro: {p['arbitro'] or 'sin dato'}{stats_str}")

    if actualizacion["partidos_sin_terminar"]:
        print(f"\n  Sin terminar todavía ({len(actualizacion['partidos_sin_terminar'])}):")
        for p in actualizacion["partidos_sin_terminar"]:
            print(f"    {p['local']} vs {p['visitante']} — estado: {p['estado']}")

    if actualizacion["equipos_no_reconocidos"]:
        print(f"\n  ⚠️ EQUIPOS NO RECONOCIDOS (revisar MAPA_NOMBRES_API_A_PROYECTO): "
              f"{actualizacion['equipos_no_reconocidos']}")


if __name__ == "__main__":
    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        print("Configura la variable de entorno API_FOOTBALL_KEY primero.")
        sys.exit(1)

    if "--buscar-liga" in sys.argv:
        candidatos = buscar_league_id(api_key)
        print("Ligas candidatas encontradas en México:")
        for c in candidatos:
            print(f"  id={c['id']:<6} {c['nombre']:<25} temporadas: {c['temporadas']}")
        sys.exit(0)

    jornada = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    actualizacion = generar_actualizacion_pendiente(api_key, jornada)
    imprimir_reporte(actualizacion)
