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
    Trae las cuotas 1X2 (h2h) Y Total de Goles (totals) de todos los
    partidos de Liga MX actualmente listados por la API (solo
    próximos/en curso — The Odds API no expone partidos ya jugados en
    el endpoint de odds en vivo).

    Nota sobre totals: confirmado con una consulta real el 31/ago/2026
    que SÍ hay cobertura de totals para Liga MX (líneas típicas: 2.5,
    2.75, 3.0, 3.25, 3.5 según la casa) — la documentación general de
    la API sugiere que totals está "limitado a deportes de EE.UU.", pero
    eso no aplicó en la práctica para este sport_key. Ninguna casa
    consultada ofreció una línea de 0.5 goles — el modelo puede seguir
    calculando que Over 0.5 es 95%+ probable, pero esa selección no es
    apostable en ninguna casa real, así que analizar_apuestas() debe
    evitar mostrarla como value bet (ver calcular_value_bet_totales()).

    Costo: 2 créditos por consulta (1 mercado h2h + 1 mercado totals,
    1 región) — de sobra dentro del plan gratis de 500/mes.

    sport_key: opcional — si se omite, usa el key confirmado
    SPORT_KEY_LIGAMX ("soccer_mexico_ligamx") directamente, sin gastar
    una consulta extra en _buscar_sport_key_ligamx().

    Devuelve una lista de dicts, uno por partido:
        [{"home_team": str, "away_team": str, "commence_time": str,
          "cuotas": {"home": float, "draw": float, "away": float, "casa": str},
          "cuotas_totales": [{"point": float, "over": float, "under": float, "casa": str}, ...]},
         ...]
    "cuotas_totales" es una lista (puede haber varias líneas distintas
    entre casas — 2.5 en una, 3.0 en otra) ordenada por "point" ascendente.
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
                "markets": "h2h,totals",
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
            "cuotas_totales": _extraer_cuotas_totales(p),
        })
    return resultado


def _extraer_cuotas_totales(partido: dict) -> list:
    """
    Extrae todas las líneas de Total de Goles (mercado "totals") que
    trae el partido, una entrada por (casa, point) distinto — a
    diferencia de h2h, aquí NO se elige "la mejor casa" porque cada casa
    puede ofrecer una línea (point) distinta, y el objetivo es poder
    verificar contra CUALQUIER línea real disponible, no solo una.

    Devuelve lista ordenada por "point" ascendente:
        [{"point": 2.5, "over": 1.51, "under": 2.38, "casa": "Pinnacle"}, ...]
    Lista vacía si el partido no trae mercado totals en ninguna casa.
    """
    lineas = []
    for b in partido.get("bookmakers", []):
        mercado_totals = next((m for m in b.get("markets", []) if m.get("key") == "totals"), None)
        if not mercado_totals:
            continue
        outcomes = {o.get("name"): (o.get("price"), o.get("point")) for o in mercado_totals.get("outcomes", [])}
        over_price, point_over = outcomes.get("Over", (None, None))
        under_price, point_under = outcomes.get("Under", (None, None))
        if over_price is None or under_price is None or point_over is None:
            continue
        lineas.append({
            "point": point_over,
            "over": over_price,
            "under": under_price,
            "casa": b.get("title", b.get("key")),
        })
    lineas.sort(key=lambda l: l["point"])
    return lineas


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


def calcular_value_bet_totales(linea_modelo: float, direccion: str, cuotas_totales: list) -> dict:
    """
    Verifica si una línea de Total de Goles que el modelo quiere
    recomendar (ej. "Over 0.5", "Over 2.5") es REALMENTE apostable en
    alguna casa real, y si es así, calcula su EV — resuelve el problema
    de que el modelo puede calcular con alta confianza un mercado que
    ninguna casa ofrece (confirmado con datos reales: ninguna casa
    consultada tiene línea de 0.5 goles, la más baja disponible ronda
    2.5).

    linea_modelo: el número de la línea que evaluó el modelo (0.5, 1.5,
    2.5, 3.5 — los que ya generan analizar_apuestas()).
    direccion: "over" o "under".
    cuotas_totales: salida de obtener_cuotas_jornada()[i]["cuotas_totales"].

    Busca la línea real con el "point" MÁS CERCANO a linea_modelo, con
    tolerancia de ±0.25 (para permitir 2.5 vs 2.75 de casas distintas
    como "razonablemente la misma línea", pero NO 0.5 vs 2.5, que son
    apuestas completamente distintas en la práctica).

    Devuelve:
        {"apostable": bool, "point_real": float | None, "ev_pct": float | None,
         "prob_implicita_pct": float | None, "tiene_valor": bool, "casa": str | None}
    "apostable": False cuando ninguna casa ofrece una línea suficientemente
    cercana — en ese caso el resto de los campos son None y
    "tiene_valor" es False, para que el llamador sepa que debe evitar
    presentar esa selección como una recomendación accionable con cuota.
    """
    TOLERANCIA_LINEA = 0.25
    if not cuotas_totales:
        return {"apostable": False, "point_real": None, "ev_pct": None,
                "prob_implicita_pct": None, "tiene_valor": False, "casa": None}

    mas_cercana = min(cuotas_totales, key=lambda l: abs(l["point"] - linea_modelo))
    if abs(mas_cercana["point"] - linea_modelo) > TOLERANCIA_LINEA:
        return {"apostable": False, "point_real": mas_cercana["point"], "ev_pct": None,
                "prob_implicita_pct": None, "tiene_valor": False, "casa": None}

    # Esto requiere que el llamador ya sepa la probabilidad del modelo
    # PARA ESA LÍNEA REAL (no la línea original) — se resuelve en
    # liga_mx_algoritmo.analizar_apuestas(), que tiene acceso directo a
    # las probabilidades de simular_partido() para cualquier línea.
    cuota = mas_cercana["over"] if direccion == "over" else mas_cercana["under"]
    return {
        "apostable": True,
        "point_real": mas_cercana["point"],
        "cuota": cuota,
        "casa": mas_cercana["casa"],
    }


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
