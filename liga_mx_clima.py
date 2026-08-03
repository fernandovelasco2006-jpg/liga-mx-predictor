"""
liga_mx_clima.py — Integración con Visual Crossing Weather API para traer
temperatura, humedad, viento y probabilidad de lluvia de cada partido, y
convertir eso en un factor de ajuste chico para calcular_lambdas().

Un solo endpoint sirve tanto para partidos FUTUROS (pronóstico) como para
partidos YA JUGADOS (clima histórico real) — Visual Crossing decide solo
cuál de los dos dar según si la fecha pedida ya pasó o no. No hace falta
distinguir en el código.

Plan gratis: 1,000 registros/día — de sobra para 9 partidos por jornada.
"""
import requests

BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

# ─────────────────────────────────────────────────────────────────────────
# Ciudad de la sede de cada equipo (para el geocoding de Visual Crossing).
# Mismo criterio que ALTITUD_EQUIPO en el skeleton: América, Cruz Azul,
# Atlante y Pumas comparten zona CDMX; Atlas y Guadalajara comparten
# ciudad; Tigres en Nuevo León (San Nicolás, área metropolitana de
# Monterrey).
# ─────────────────────────────────────────────────────────────────────────
CIUDAD_EQUIPO = {
    "Toluca":             "Toluca, Mexico",
    "Puebla":             "Puebla, Mexico",
    "Pachuca":            "Pachuca, Mexico",
    "Queretaro":          "Queretaro, Mexico",
    "Atletico San Luis":  "San Luis Potosi, Mexico",
    "Leon":               "Leon, Guanajuato, Mexico",
    "Necaxa":             "Aguascalientes, Mexico",
    "Guadalajara":        "Guadalajara, Mexico",
    "Atlas":              "Guadalajara, Mexico",
    "Santos Laguna":      "Torreon, Mexico",
    "FC Juarez":          "Ciudad Juarez, Mexico",
    "Monterrey":          "Monterrey, Mexico",
    "Tijuana":            "Tijuana, Mexico",
    "America":            "Mexico City, Mexico",
    "Cruz Azul":          "Mexico City, Mexico",
    "Atlante":            "Mexico City, Mexico",
    "Pumas UNAM":         "Mexico City, Mexico",
    "Tigres":             "San Nicolas de los Garza, Mexico",
}


def obtener_clima_partido(home_team: str, fecha_hora: str, api_key: str) -> dict:
    """
    Trae temperatura, humedad, viento y probabilidad de lluvia para la
    hora del partido.

    fecha_hora: mismo formato que HORARIOS_PARTIDO — "YYYY-MM-DD HH:MM".
    Funciona igual para partidos pasados (clima real, histórico) que
    futuros (pronóstico); Visual Crossing decide solo cuál dar.

    Devuelve None si no hay ciudad mapeada para el equipo, no hay
    api_key, o falla la petición por cualquier motivo — nunca truena la
    app por un problema de la API externa; simplemente se sigue sin
    ajuste de clima (factor 1.0) en ese caso.
    """
    ciudad = CIUDAD_EQUIPO.get(home_team)
    if not (ciudad and api_key and fecha_hora):
        return None
    try:
        fecha, hora = fecha_hora.split(" ")
        fecha_iso = f"{fecha}T{hora}:00"
        resp = requests.get(
            f"{BASE_URL}/{ciudad}/{fecha_iso}",
            params={
                "key": api_key,
                "unitGroup": "metric",
                "include": "hours",
                "contentType": "json",
                "elements": "datetime,temp,humidity,precipprob,windspeed,conditions",
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        dias = data.get("days", [])
        if not dias:
            return None
        dia = dias[0]
        hora_num = int(hora.split(":")[0])
        horas = dia.get("hours", [])
        bloque = next(
            (h for h in horas if h.get("datetime", "").startswith(f"{hora_num:02d}:")),
            dia,  # si no encuentra la hora exacta, usa el resumen del día completo
        )
        return {
            "temp_c": bloque.get("temp"),
            "humedad_pct": bloque.get("humidity"),
            "prob_lluvia_pct": bloque.get("precipprob"),
            "viento_kmh": bloque.get("windspeed"),
            "condiciones": bloque.get("conditions"),
        }
    except Exception:
        return None


def factor_clima(clima: dict) -> float:
    """
    Convierte el clima en un multiplicador chico para λ_home/λ_away
    (goles esperados). El clima es un factor SECUNDARIO a propósito —
    nunca debería mover la predicción tanto como Elo, forma o altitud:

      - Lluvia fuerte (prob. de lluvia >= 60% o "Rain"/"Storm" en las
        condiciones reportadas): -4% en los goles esperados — más
        errores no forzados, juego más cauteloso, menos ida y vuelta.
      - Calor + humedad extremos a la vez (temp >= 30°C Y humedad >=
        70%): -3% — más fatiga, ritmo más lento, sobre todo en el
        segundo tiempo. Solo aplica si ambas condiciones se cumplen
        juntas (el calor solo, o la humedad sola, no bastan).
      - Nada especial: sin ajuste (factor 1.0).

    Los dos ajustes se pueden combinar (lluvia Y calor extremo el mismo
    día es raro pero no imposible). Si clima es None (sin datos porque
    no hay API key, falló la petición, o no hay ciudad mapeada), siempre
    devuelve 1.0 — nunca penaliza ni favorece por falta de información.
    """
    if not clima:
        return 1.0
    factor = 1.0

    lluvia = clima.get("prob_lluvia_pct") or 0
    condiciones = (clima.get("condiciones") or "").lower()
    if lluvia >= 60 or "rain" in condiciones or "storm" in condiciones:
        factor *= 0.96

    temp = clima.get("temp_c")
    humedad = clima.get("humedad_pct")
    if temp is not None and humedad is not None and temp >= 30 and humedad >= 70:
        factor *= 0.97

    return factor
