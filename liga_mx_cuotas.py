"""
liga_mx_cuotas.py — Integración con The Odds API (the-odds-api.com) para
traer cuotas reales de casas de apuestas y calcular Value Betting: comparar
la probabilidad del modelo (simular_partido()) contra la probabilidad
implícita de la cuota real, y detectar cuándo el modelo cree que la casa
está pagando más de lo que debería.

Mismo patrón que liga_mx_clima.py: una función obtener_X() que trae el dato
crudo con manejo de errores silencioso (devuelve None ante cualquier falla
— sin api_key, sin conexión, partido no listado, etc.) y funciones aparte
que procesan ese dato. Nunca truena la app por un problema de la API
externa; sin cuota disponible, simplemente no se calcula value (no se
inventa ni se asume neutral).

Plan gratis: 500 créditos/mes — cada llamada a /v4/sports/{key}/odds que
trae TODOS los partidos de la jornada cuesta 1 crédito (no por partido),
así que una jornada de 9 partidos = 1 crédito. De sobra para consultar
varias veces por semana sin acercarse al límite.

IMPORTANTE — sport_key CONFIRMADO con una consulta real a la API el
29/ago/2026: "soccer_mexico_ligamx" (title: "Liga MX", description:
"Mexican Soccer"). Se usa como default en obtener_cuotas_jornada(); la
búsqueda dinámica en _buscar_sport_key_ligamx() se conserva como
respaldo por si el key cambiara en el futuro, pero ya no es necesaria
para el uso normal.
"""
import requests
from liga_mx_predictor_skeleton import EQUIPOS

BASE_URL = "https://api.the-odds-api.com/v4"

SPORT_KEY_LIGAMX = "soccer_mexico_ligamx"  # confirmado contra la API real, ver nota arriba

# Casa de apuestas preferida para el value betting, en orden de
# prioridad — si la primera no tiene cuota para un partido, se intenta
# con la siguiente. Pinnacle es la referencia estándar en la industria
# por ser una casa "sharp" (líneas muy ajustadas, poco margen), pero no
# siempre está disponible en la región "eu"; bet365 y williamhill como
# respaldo, ambas comunes en la cobertura europea de la API.
CASAS_PREFERIDAS = ["pinnacle", "bet365", "williamhill", "unibet"]

REGION_CUOTAS = "eu"  # eu suele traer más casas con cobertura de Liga MX que us/uk/au


def _buscar_sport_key_ligamx(api_key: str) -> str:
    """
    Consulta GET /v4/sports (no cuesta créditos) y busca la entrada de
    Liga MX por texto, sin asumir un sport_key fijo. Devuelve el key
    exacto que use la API en este momento, o None si no se encuentra o
    la petición falla.
    """
    if not api_key:
        return None
    try:
        resp = requests.get(
            f"{BASE_URL}/sports",
            params={"apiKey": api_key},
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        deportes = resp.json()
        for d in deportes:
            titulo = (d.get("title") or "").lower()
            grupo = (d.get("group") or "").lower()
            key = (d.get("key") or "").lower()
            descripcion = (d.get("description") or "").lower()
            texto = f"{titulo} {grupo} {key} {descripcion}"
            if "liga mx" in texto or ("mexico" in texto and "soccer" in texto):
                return d.get("key")
        return None
    except Exception:
        return None


def obtener_cuotas_jornada(api_key: str, sport_key: str = None) -> list:
    """
    Trae las cuotas 1X2 (mercado h2h) de todos los partidos de Liga MX
    actualmente listados por la API (solo próximos/en curso — The Odds
    API no expone partidos ya jugados en el endpoint de odds en vivo).

    sport_key: opcional — si se omite, usa el key confirmado
    SPORT_KEY_LIGAMX ("soccer_mexico_ligamx") directamente, sin gastar
    una consulta extra en _buscar_sport_key_ligamx().

    Devuelve una lista de dicts, uno por partido:
        [{"home_team": str, "away_team": str, "commence_time": str,
          "cuotas": {"home": float, "draw": float, "away": float, "casa": str}},
         ...]
    Lista vacía si no hay api_key, no se encuentra el sport_key, o la
    petición falla por cualquier motivo — nunca truena la app.
    """
    if not api_key:
        return []
    key = sport_key or SPORT_KEY_LIGAMX
    try:
        resp = requests.get(
            f"{BASE_URL}/sports/{key}/odds",
            params={
                "apiKey": api_key,
                "regions": REGION_CUOTAS,
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        partidos = resp.json()
    except Exception:
        return []

    resultado = []
    for p in partidos:
        cuotas = _extraer_mejor_cuota_h2h(p)
        if cuotas is None:
            continue
        home_interno = emparejar_equipo(p.get("home_team", ""))
        away_interno = emparejar_equipo(p.get("away_team", ""))
        if home_interno is None or away_interno is None:
            # No se pudo emparejar con certeza con un equipo interno —
            # se omite en vez de arriesgar cruzar mal dos equipos
            # distintos. No debería pasar con los 18 equipos de Liga MX
            # ya cubiertos, pero sirve de red de seguridad si algún
            # nombre cambia de formato en la API en el futuro.
            continue
        resultado.append({
            "home_team": home_interno,
            "away_team": away_interno,
            "commence_time": p.get("commence_time"),
            "cuotas": cuotas,
        })
    return resultado


def _extraer_mejor_cuota_h2h(partido: dict) -> dict:
    """
    De la lista de bookmakers que trae un partido, elige uno según
    CASAS_PREFERIDAS (la primera que aparezca disponible); si ninguna de
    las preferidas está, usa la primera casa que sí traiga el mercado
    h2h completo (los 3 resultados). Devuelve None si el partido no
    trae ningún bookmaker con h2h completo.
    """
    bookmakers = partido.get("bookmakers", [])
    if not bookmakers:
        return None

    por_key = {b.get("key"): b for b in bookmakers}
    orden = CASAS_PREFERIDAS + [k for k in por_key if k not in CASAS_PREFERIDAS]

    for casa_key in orden:
        b = por_key.get(casa_key)
        if not b:
            continue
        mercado_h2h = next((m for m in b.get("markets", []) if m.get("key") == "h2h"), None)
        if not mercado_h2h:
            continue
        outcomes = {o.get("name"): o.get("price") for o in mercado_h2h.get("outcomes", [])}
        home = outcomes.get(partido.get("home_team"))
        away = outcomes.get(partido.get("away_team"))
        draw = outcomes.get("Draw")
        if home and away and draw:
            return {"home": home, "draw": draw, "away": away, "casa": b.get("title", casa_key)}
    return None


def emparejar_equipo(nombre_odds_api: str, mapa_nombres: dict = None) -> str:
    """
    The Odds API devuelve nombres de equipo casi idénticos a los internos
    (EQUIPOS en liga_mx_predictor_skeleton.py), pero con acentos en varios
    casos ("Querétaro", "América", "Atlético San Luis", "FC Juárez",
    "León") y un par de variantes de sufijo ("Atlante FC" vs "Atlante",
    "Pumas" vs "Pumas UNAM") — confirmado con una consulta real a la API
    el 29/ago/2026 (ver MAPA_NOMBRES_ODDS_API).

    Primero intenta un match DIRECTO contra EQUIPOS (la mayoría de los 18
    equipos ya vienen con el nombre exactamente igual — Atlas, Pachuca,
    Guadalajara, Toluca, Monterrey, Puebla, Tigres, Santos Laguna, Cruz
    Azul, Necaxa, Tijuana — y no deben pasar por ninguna traducción).
    Solo si eso falla, recurre a MAPA_NOMBRES_ODDS_API normalizando
    acentos. Devuelve None si no hay match — mejor no adivinar que
    cruzar mal dos equipos distintos.
    """
    if nombre_odds_api in EQUIPOS:
        return nombre_odds_api

    if mapa_nombres is None:
        mapa_nombres = MAPA_NOMBRES_ODDS_API
    if nombre_odds_api in mapa_nombres:
        return mapa_nombres[nombre_odds_api]

    normalizado = _quitar_acentos(nombre_odds_api).lower().strip()
    for clave, interno in mapa_nombres.items():
        if _quitar_acentos(clave).lower().strip() == normalizado:
            return interno
    for clave, interno in mapa_nombres.items():
        clave_norm = _quitar_acentos(clave).lower()
        if clave_norm in normalizado or normalizado in clave_norm:
            return interno
    return None


def _quitar_acentos(texto: str) -> str:
    """Quita acentos comunes del español para comparar nombres de equipo
    sin depender de que ambos lados usen la misma convención de tildes."""
    reemplazos = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return texto.translate(reemplazos)


# ─────────────────────────────────────────────────────────────────────────
# MAPA_NOMBRES_ODDS_API — traduce el nombre de equipo tal como lo entrega
# The Odds API (columna izquierda, con sus acentos/variantes reales) al
# nombre interno que usa el resto del proyecto (columna derecha, EQUIPOS
# en liga_mx_predictor_skeleton.py). CONFIRMADO con una consulta real a
# /v4/sports/soccer_mexico_ligamx/odds/ el 29/ago/2026 — no son nombres
# adivinados. emparejar_equipo() ya normaliza acentos solo, así que este
# mapa solo necesita cubrir los casos con acento o sufijo distinto; los
# 11 equipos con nombre idéntico (Atlas, Pachuca, Guadalajara, Toluca,
# Monterrey, Puebla, Tigres, Santos Laguna, Cruz Azul, Necaxa, Tijuana)
# no necesitan entrada — el match exacto ya los resuelve directo.
# ─────────────────────────────────────────────────────────────────────────
MAPA_NOMBRES_ODDS_API = {
    "Querétaro":            "Queretaro",
    "América":              "America",
    "Atlético San Luis":    "Atletico San Luis",
    "FC Juárez":            "FC Juarez",
    "León":                 "Leon",
    "Atlante FC":           "Atlante",
    "Pumas":                "Pumas UNAM",
}


UMBRAL_VALUE_EV = 5.0  # % mínimo de EV para marcar una apuesta como "con valor"


def calcular_value_bet(prob_modelo_pct: float, cuota_decimal: float) -> dict:
    """
    Calcula el Expected Value (EV) de apostar a un resultado, comparando
    la probabilidad del modelo contra la cuota decimal real de una casa.

        EV = (prob_modelo × cuota_decimal) - 1

    Ejemplo: el modelo dice 70% de que gane el local, la casa paga 1.60
    por esa selección → EV = (0.70 × 1.60) - 1 = 0.12 → 12% de valor
    esperado por unidad apostada, en promedio, si la probabilidad del
    modelo es correcta.

    También calcula la probabilidad IMPLÍCITA de la cuota (1/cuota) para
    poder comparar directamente "lo que cree el modelo" vs. "lo que
    implica la casa" — la brecha entre ambas es la fuente del EV.

    Devuelve:
        {"ev_pct": float, "prob_implicita_pct": float, "tiene_valor": bool}
    tiene_valor = True solo si ev_pct > UMBRAL_VALUE_EV (5.0 por defecto,
    ver la constante) — un EV positivo pero chico no compensa el margen
    de error real del modelo.
    """
    if cuota_decimal is None or cuota_decimal <= 1.0 or prob_modelo_pct is None:
        return {"ev_pct": None, "prob_implicita_pct": None, "tiene_valor": False}

    prob_modelo = prob_modelo_pct / 100.0
    prob_implicita = 1.0 / cuota_decimal
    ev = (prob_modelo * cuota_decimal) - 1.0
    ev_pct = round(ev * 100, 1)

    return {
        "ev_pct": ev_pct,
        "prob_implicita_pct": round(prob_implicita * 100, 1),
        "tiene_valor": ev_pct > UMBRAL_VALUE_EV,
    }
