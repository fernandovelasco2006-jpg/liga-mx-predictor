# ─────────────────────────────────────────────────────────────────────────
# LIGA MX · APERTURA 2026 · ALGORITMO — calcular_lambdas() + simular_temporada()
#
# Este módulo asume que ya importaste desde tu liga_mx_predictor_skeleton.py:
#   EQUIPOS, ELO, ALTITUD_EQUIPO, PARTIDOS, HORARIOS_PARTIDO,
#   ARBITROS_LIGA_MX, ARBITRO_DEFAULT
#
# Para probarlo standalone, este archivo hace el import directo del
# skeleton. En tu app.py final, simplemente pega ambos módulos juntos o
# usa "from liga_mx_predictor_skeleton import *".
# ─────────────────────────────────────────────────────────────────────────
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta

from liga_mx_predictor_skeleton import (
    EQUIPOS, ELO, ALTITUD_EQUIPO, PARTIDOS, HORARIOS_PARTIDO,
    ARBITROS_LIGA_MX, ARBITRO_DEFAULT,
)

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ PLACEHOLDER — FUERZA DE ATAQUE Y DEFENSA POR EQUIPO
# Todavía no tenemos goles-a-favor / goles-en-contra reales del Clausura
# 2026 (a diferencia del Mundial, donde FORMA_MUNDIAL sí eran datos
# reales de J1-J3). Por ahora los derivo del ELO con esta lógica:
#   - Equipo con ELO por encima del promedio de la liga → ataca más y
#     defiende mejor (concede menos) que el promedio.
#   - Equipo por debajo del promedio → lo contrario.
# EN CUANTO TENGAS los promedios reales de goles a favor/en contra por
# partido de cada equipo (pídeselo a Perplexity: "goles a favor y en
# contra promedio por partido de cada equipo de Liga MX en el Clausura
# 2026"), reemplaza este bloque completo por un diccionario con esos
# valores reales — el resto del algoritmo no necesita cambiar.
# ─────────────────────────────────────────────────────────────────────────
LIGA_PROMEDIO_GOLES = 1.35   # goles por equipo por partido, típico de Liga MX (~2.7 goles/partido total)
_elo_promedio = sum(ELO.values()) / len(ELO)

FUERZA_ATAQUE = {}
FUERZA_DEFENSA = {}
for equipo, elo in ELO.items():
    diff = elo - _elo_promedio
    # ataque: entre ~0.75x y ~1.30x el promedio de la liga según qué tan
    # arriba/abajo esté su ELO (tope +-150 puntos de diferencia)
    factor_ataque = 1.0 + max(min(diff, 150), -150) / 500
    # defensa: goles que CONCEDE el equipo (no lo que ataca). Equipo
    # fuerte concede menos → factor < 1.0
    factor_defensa = 1.0 - max(min(diff, 150), -150) / 650
    FUERZA_ATAQUE[equipo] = round(LIGA_PROMEDIO_GOLES * factor_ataque, 3)
    FUERZA_DEFENSA[equipo] = round(LIGA_PROMEDIO_GOLES * factor_defensa, 3)

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ PLACEHOLDER — FECHAS DE LEAGUES CUP POR EQUIPO
# Vacío por ahora. Llénalo cuando tengas el calendario de Leagues Cup
# 2026 confirmado para los equipos de Liga MX que participan (no todos
# los 18 equipos van a Leagues Cup necesariamente — verifica cuáles).
# Formato: {"America": ["2026-08-05", "2026-08-08", ...], ...}
# ─────────────────────────────────────────────────────────────────────────
LEAGUES_CUP_FECHAS = {}
FACTOR_FATIGA_LEAGUES_CUP = 0.90   # -10% lambda ofensivo, como pediste

ALTITUD_UMBRAL = 1700       # metros — a partir de aquí se considera "altura"
BONUS_ALTITUD_LOCAL = 0.20  # +0.2 lambda para el local en altura, como pediste
EQUIPOS_ACLIMATADOS_ALTURA = {
    # Equipos que también juegan de local en altura, y por lo tanto no
    # sufren tanto la desventaja de visitar otra ciudad alta.
    "Toluca", "Pachuca", "Queretaro", "Atletico San Luis", "Leon",
    "Necaxa", "Pumas UNAM", "America", "Cruz Azul", "Atlante",
}


def _buscar_arbitro(home_team: str, away_team: str):
    """Busca el árbitro asignado a un partido dentro de PARTIDOS."""
    for local, visit, jornada, estadio, resultado, arbitro in PARTIDOS:
        if local == home_team and visit == away_team:
            return arbitro
    return None


def _buscar_fecha_partido(home_team: str, away_team: str):
    """Busca la fecha/hora del partido en HORARIOS_PARTIDO."""
    horario = HORARIOS_PARTIDO.get((home_team, away_team))
    if not horario:
        return None
    try:
        return datetime.strptime(horario, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _jugo_leagues_cup_reciente(equipo: str, fecha_partido: datetime) -> bool:
    """True si el equipo jugó Leagues Cup en los 7 días previos a fecha_partido."""
    if fecha_partido is None:
        return False
    fechas = LEAGUES_CUP_FECHAS.get(equipo, [])
    for f in fechas:
        try:
            f_dt = datetime.strptime(f, "%Y-%m-%d")
        except ValueError:
            continue
        if timedelta(0) <= (fecha_partido - f_dt) <= timedelta(days=7):
            return True
    return False


def _forma_real_liga_mx() -> dict:
    """
    Calcula (goles_favor, goles_contra, partidos_jugados) REALES por
    equipo, a partir de los partidos que ya tienen resultado en
    PARTIDOS. Se recalcula cada vez que se llama (barato: 153 filas) —
    así conforme le vayas dando resultados de más jornadas, el modelo
    se corrige solo sin que tengas que tocar código.
    """
    forma = {eq: [0, 0, 0] for eq in EQUIPOS}
    for local, visit, jornada, estadio, resultado, arbitro in PARTIDOS:
        if resultado is None:
            continue
        gh, ga = resultado
        forma[local][0] += gh; forma[local][1] += ga; forma[local][2] += 1
        forma[visit][0] += ga; forma[visit][1] += gh; forma[visit][2] += 1
    return forma


def calcular_lambdas(home_team: str, away_team: str,
                      peso_elo: float = 1.0,
                      peso_altitud: float = 1.0,
                      peso_arbitro: float = 1.0) -> tuple:
    """
    Calcula (lambda_home, lambda_away): la tasa esperada de goles para
    cada equipo, combinando:
      1. Ataque/Defensa (relativo al ELO, ver nota de PLACEHOLDER arriba)
      2. Forma real — goles reales anotados/recibidos en partidos ya
         jugados de este torneo (se auto-actualiza con cada resultado
         que agregues a PARTIDOS)
      3. Factor altitud (ventaja para el local en ciudades altas)
      4. Factor árbitro (promedio de tarjetas → intensidad del partido)
      5. Factor fatiga (Leagues Cup en los últimos 7 días)

    peso_elo, peso_altitud, peso_arbitro: multiplicadores para ajustar
    cuánto pesa cada factor en el resultado final. 1.0 = calibración por
    defecto (la que ya probamos). 0.0 = el factor no tiene efecto.
    2.0 = el doble de efecto que el calibrado. Pensados para conectarse
    directo a st.slider en la interfaz — sin tocar variables globales.

    Devuelve (lambda_home, lambda_away) listos para simular goles con
    una distribución de Poisson.
    """
    # 1. Ataque / Defensa ────────────────────────────────────────────
    # peso_elo interpola entre "todos los equipos son iguales" (peso=0)
    # y "la calibración ELO completa" (peso=1); peso=2 duplica el efecto.
    ataque_home = LIGA_PROMEDIO_GOLES + peso_elo * (FUERZA_ATAQUE.get(home_team, LIGA_PROMEDIO_GOLES) - LIGA_PROMEDIO_GOLES)
    defensa_home = LIGA_PROMEDIO_GOLES + peso_elo * (FUERZA_DEFENSA.get(home_team, LIGA_PROMEDIO_GOLES) - LIGA_PROMEDIO_GOLES)
    ataque_away = LIGA_PROMEDIO_GOLES + peso_elo * (FUERZA_ATAQUE.get(away_team, LIGA_PROMEDIO_GOLES) - LIGA_PROMEDIO_GOLES)
    defensa_away = LIGA_PROMEDIO_GOLES + peso_elo * (FUERZA_DEFENSA.get(away_team, LIGA_PROMEDIO_GOLES) - LIGA_PROMEDIO_GOLES)

    # Modelo clásico tipo Dixon-Coles: goles esperados del local
    # dependen de SU ataque y de la defensa del VISITANTE (y viceversa).
    lam_home = (ataque_home / LIGA_PROMEDIO_GOLES) * (defensa_away / LIGA_PROMEDIO_GOLES) * LIGA_PROMEDIO_GOLES
    lam_away = (ataque_away / LIGA_PROMEDIO_GOLES) * (defensa_home / LIGA_PROMEDIO_GOLES) * LIGA_PROMEDIO_GOLES

    # 1b. Forma real — ajusta con goles reales, tope +-8% (mismo criterio
    # que usabas en FORMA_MUNDIAL del Mundial-predictor)
    forma = _forma_real_liga_mx()
    for equipo in (home_team, away_team):
        gf, gc, pj = forma.get(equipo, (0, 0, 0))
        if pj > 0:
            avg_gf = gf / pj
            avg_gc = gc / pj
            f_of = max(1.0 + min((avg_gf - LIGA_PROMEDIO_GOLES) / LIGA_PROMEDIO_GOLES, 0.08), 0.92)
            f_def = max(1.0 + min((avg_gc - LIGA_PROMEDIO_GOLES) / LIGA_PROMEDIO_GOLES, 0.08), 0.92)
            if equipo == home_team:
                lam_home *= f_of
                lam_away *= f_def
            else:
                lam_away *= f_of
                lam_home *= f_def

    # Ventaja de localía estándar (típico ~10-15% en fútbol de liga)
    lam_home *= 1.12

    # 2. Factor altitud ───────────────────────────────────────────────
    alt_local = ALTITUD_EQUIPO.get(home_team)
    if alt_local is not None and alt_local >= ALTITUD_UMBRAL:
        bono = BONUS_ALTITUD_LOCAL * peso_altitud
        if away_team not in EQUIPOS_ACLIMATADOS_ALTURA:
            # el visitante no está acostumbrado a la altura → el local
            # se beneficia más de lo normal
            lam_home += bono
        else:
            # ambos equipos están acostumbrados a la altura → bonus reducido
            lam_home += bono * 0.3

    # 3. Factor árbitro ─────────────────────────────────────────────
    # Un árbitro que reparte muchas tarjetas normalmente corresponde a
    # partidos más cortados/físicos → baja un poco el ritmo ofensivo de
    # ambos equipos (más faltas, menos fluidez, defensas más agresivas).
    arbitro = _buscar_arbitro(home_team, away_team)
    prom_amarillas, _partidos_arb = ARBITROS_LIGA_MX.get(arbitro, (ARBITRO_DEFAULT[0], 0))
    # Liga MX promedia ~4.0-4.5 amarillas/partido; usamos eso como base
    PROMEDIO_LIGA_AMARILLAS = 4.3
    desviacion = prom_amarillas - PROMEDIO_LIGA_AMARILLAS
    # cada amarilla de más sobre el promedio recorta ~1.5% el ritmo ofensivo,
    # escalado por peso_arbitro, con tope de +-10%*peso_arbitro (máx 30%)
    tope = min(0.10 * peso_arbitro, 0.30)
    factor_arbitro = 1.0 - max(min(desviacion * 0.015 * peso_arbitro, tope), -tope)
    lam_home *= factor_arbitro
    lam_away *= factor_arbitro

    # 4. Factor fatiga (Leagues Cup) ──────────────────────────────────
    fecha_partido = _buscar_fecha_partido(home_team, away_team)
    if _jugo_leagues_cup_reciente(home_team, fecha_partido):
        lam_home *= FACTOR_FATIGA_LEAGUES_CUP
    if _jugo_leagues_cup_reciente(away_team, fecha_partido):
        lam_away *= FACTOR_FATIGA_LEAGUES_CUP

    return max(lam_home, 0.15), max(lam_away, 0.15)


# ─────────────────────────────────────────────────────────────────────────
# simular_temporada()
# ─────────────────────────────────────────────────────────────────────────
def _jugar_partido(home_team: str, away_team: str, rng=None,
                    peso_elo: float = 1.0, peso_altitud: float = 1.0,
                    peso_arbitro: float = 1.0) -> tuple:
    """Simula UN resultado (goles_home, goles_away) usando Poisson."""
    if rng is None:
        rng = np.random.default_rng()
    lam_h, lam_a = calcular_lambdas(home_team, away_team,
                                     peso_elo=peso_elo,
                                     peso_altitud=peso_altitud,
                                     peso_arbitro=peso_arbitro)
    goles_h = rng.poisson(lam_h)
    goles_a = rng.poisson(lam_a)
    return int(goles_h), int(goles_a)


def _tabla_vacia() -> dict:
    return {
        equipo: {"PJ": 0, "PG": 0, "PE": 0, "PP": 0, "GF": 0, "GC": 0, "DG": 0, "PTS": 0}
        for equipo in EQUIPOS
    }


def _actualizar_tabla(tabla, home, away, gh, ga):
    tabla[home]["PJ"] += 1
    tabla[away]["PJ"] += 1
    tabla[home]["GF"] += gh
    tabla[home]["GC"] += ga
    tabla[away]["GF"] += ga
    tabla[away]["GC"] += gh
    if gh > ga:
        tabla[home]["PG"] += 1
        tabla[home]["PTS"] += 3
        tabla[away]["PP"] += 1
    elif gh < ga:
        tabla[away]["PG"] += 1
        tabla[away]["PTS"] += 3
        tabla[home]["PP"] += 1
    else:
        tabla[home]["PE"] += 1
        tabla[away]["PE"] += 1
        tabla[home]["PTS"] += 1
        tabla[away]["PTS"] += 1
    tabla[home]["DG"] = tabla[home]["GF"] - tabla[home]["GC"]
    tabla[away]["DG"] = tabla[away]["GF"] - tabla[away]["GC"]


def _ordenar_tabla(tabla: dict) -> list:
    """Puntos > diferencia de goles > goles a favor, como pediste."""
    filas = [{"equipo": eq, **stats} for eq, stats in tabla.items()]
    filas.sort(key=lambda f: (f["PTS"], f["DG"], f["GF"]), reverse=True)
    for i, f in enumerate(filas, start=1):
        f["posicion"] = i
    return filas


def _jugar_serie_ida_vuelta(equipo_A: str, equipo_B: str, seed_A: int, seed_B: int, rng=None,
                             peso_elo: float = 1.0, peso_altitud: float = 1.0,
                             peso_arbitro: float = 1.0) -> dict:
    """
    Serie a ida y vuelta. El peor posicionado (seed más alto/número más
    grande) juega la IDA de local; el mejor posicionado juega la VUELTA
    de local (ventaja de local en el partido decisivo). Si el marcador
    global queda empatado, avanza el mejor posicionado de la fase
    regular (regla vigente de Liga MX, sin penales).
    """
    if seed_A < seed_B:
        mejor, peor = equipo_A, equipo_B
    else:
        mejor, peor = equipo_B, equipo_A

    kwargs = dict(peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)
    gh1, ga1 = _jugar_partido(peor, mejor, rng, **kwargs)     # ida: local el peor posicionado
    gh2, ga2 = _jugar_partido(mejor, peor, rng, **kwargs)     # vuelta: local el mejor posicionado

    goles_mejor = ga1 + gh2
    goles_peor = gh1 + ga2

    if goles_mejor > goles_peor:
        ganador = mejor
    elif goles_peor > goles_mejor:
        ganador = peor
    else:
        ganador = mejor  # empate global → avanza el mejor posicionado

    return {
        "equipo_A": equipo_A, "equipo_B": equipo_B,
        "ida": f"{peor} {gh1}-{ga1} {mejor}",
        "vuelta": f"{mejor} {gh2}-{ga2} {peor}",
        "marcador_global": f"{mejor} {goles_mejor}-{goles_peor} {peor}",
        "ganador": ganador,
    }


def simular_temporada(rng=None,
                       peso_elo: float = 1.0,
                       peso_altitud: float = 1.0,
                       peso_arbitro: float = 1.0) -> dict:
    """
    Simula la fase regular completa (17 jornadas) + Liguilla completa.

    peso_elo, peso_altitud, peso_arbitro: se pasan directo a
    calcular_lambdas() en cada partido — pensados para conectarse a
    st.slider() en la interfaz sin usar estado global.

    Devuelve:
        {
          "tabla_final": [...],        # 18 equipos ordenados
          "liguilla": {
              "cuartos": [...],
              "semis": [...],
              "final": {...},
              "campeon": "Equipo",
          }
        }
    """
    if rng is None:
        rng = np.random.default_rng()

    kwargs = dict(peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)

    tabla = _tabla_vacia()
    for home, away, jornada, estadio, resultado_real, arbitro in PARTIDOS:
        if resultado_real is not None:
            # partido ya jugado en la vida real → usa el resultado real
            gh, ga = resultado_real
        else:
            gh, ga = _jugar_partido(home, away, rng, **kwargs)
        _actualizar_tabla(tabla, home, away, gh, ga)

    tabla_final = _ordenar_tabla(tabla)
    top8 = tabla_final[:8]
    seed = {fila["equipo"]: fila["posicion"] for fila in top8}

    # ── Cuartos de Final: 1v8, 2v7, 3v6, 4v5 ───────────────────────────
    pares_cuartos = [
        (top8[0]["equipo"], top8[7]["equipo"]),
        (top8[1]["equipo"], top8[6]["equipo"]),
        (top8[2]["equipo"], top8[5]["equipo"]),
        (top8[3]["equipo"], top8[4]["equipo"]),
    ]
    cuartos = [
        _jugar_serie_ida_vuelta(a, b, seed[a], seed[b], rng, **kwargs)
        for a, b in pares_cuartos
    ]

    # ── Semifinales: RECLASIFICACIÓN — mejor posicionado restante vs peor ──
    avanzan_cuartos = [c["ganador"] for c in cuartos]
    avanzan_ordenados = sorted(avanzan_cuartos, key=lambda eq: seed[eq])
    pares_semis = [
        (avanzan_ordenados[0], avanzan_ordenados[3]),
        (avanzan_ordenados[1], avanzan_ordenados[2]),
    ]
    semis = [
        _jugar_serie_ida_vuelta(a, b, seed[a], seed[b], rng, **kwargs)
        for a, b in pares_semis
    ]

    # ── Final ───────────────────────────────────────────────────────
    finalistas = [s["ganador"] for s in semis]
    final = _jugar_serie_ida_vuelta(finalistas[0], finalistas[1],
                                     seed[finalistas[0]], seed[finalistas[1]], rng, **kwargs)

    return {
        "tabla_final": tabla_final,
        "liguilla": {
            "cuartos": cuartos,
            "semis": semis,
            "final": final,
            "campeon": final["ganador"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# BONUS — simular_temporada_montecarlo()
# No lo pediste explícitamente, pero es el paso natural siguiente: correr
# simular_temporada() N veces para obtener probabilidades reales de
# "hacer Liguilla", "ser campeón", etc. — igual que hacías con las 10M
# simulaciones por partido en el Mundial, pero aquí cada simulación es
# una TEMPORADA completa.
# ─────────────────────────────────────────────────────────────────────────
def simular_temporada_montecarlo(n: int = 1000,
                                  peso_elo: float = 1.0,
                                  peso_altitud: float = 1.0,
                                  peso_arbitro: float = 1.0) -> dict:
    rng = np.random.default_rng()
    conteo_liguilla = defaultdict(int)
    conteo_campeon = defaultdict(int)
    suma_posicion = defaultdict(int)

    for _ in range(n):
        resultado = simular_temporada(rng, peso_elo=peso_elo,
                                       peso_altitud=peso_altitud,
                                       peso_arbitro=peso_arbitro)
        for fila in resultado["tabla_final"][:8]:
            conteo_liguilla[fila["equipo"]] += 1
        for fila in resultado["tabla_final"]:
            suma_posicion[fila["equipo"]] += fila["posicion"]
        conteo_campeon[resultado["liguilla"]["campeon"]] += 1

    return {
        "prob_liguilla": {eq: round(conteo_liguilla[eq] / n * 100, 1) for eq in EQUIPOS},
        "prob_campeon": {eq: round(conteo_campeon.get(eq, 0) / n * 100, 1) for eq in EQUIPOS},
        "posicion_promedio": {eq: round(suma_posicion[eq] / n, 1) for eq in EQUIPOS},
    }



# ─────────────────────────────────────────────────────────────────────────
# simular_partido() — Monte Carlo de UN partido, 10,000,000 simulaciones
# por defecto (igual que el Mundial), usando calcular_lambdas().
# ─────────────────────────────────────────────────────────────────────────
from collections import Counter
from liga_mx_predictor_skeleton import CORNERS_EQUIPO, CORNERS_DEFAULT

PROMEDIO_LIGA_AMARILLAS = 4.3
PROMEDIO_LIGA_ROJAS = 0.15   # ⚠️ placeholder — no hay dato real de rojas por árbitro todavía


def _tarjetas_esperadas(home_team: str, away_team: str, peso_arbitro: float = 1.0) -> tuple:
    """Devuelve (amarillas_esperadas, rojas_esperadas) para el partido."""
    arbitro = _buscar_arbitro(home_team, away_team)
    prom_amarillas, _n = ARBITROS_LIGA_MX.get(arbitro, (ARBITRO_DEFAULT[0], 0))
    if arbitro and arbitro in ARBITROS_LIGA_MX:
        amarillas_esp = prom_amarillas
    else:
        desviacion = (prom_amarillas - PROMEDIO_LIGA_AMARILLAS) * peso_arbitro
        amarillas_esp = PROMEDIO_LIGA_AMARILLAS + desviacion * 0.3
    amarillas_esp = max(amarillas_esp, 1.5)
    # rojas escaladas proporcionalmente al "carácter" del árbitro (placeholder,
    # reemplazar cuando tengas promedio real de rojas por árbitro)
    rojas_esp = PROMEDIO_LIGA_ROJAS * (amarillas_esp / PROMEDIO_LIGA_AMARILLAS)
    return amarillas_esp, rojas_esp


def simular_partido(home_team: str, away_team: str, n: int = 10_000_000,
                     peso_elo: float = 1.0, peso_altitud: float = 1.0,
                     peso_arbitro: float = 1.0) -> dict:
    """
    Corre N simulaciones Monte Carlo de UN partido (10,000,000 por
    defecto, igual que en tu predictor del Mundial) y agrega
    probabilidades por mercado: 1X2, doble oportunidad, total de goles,
    ambos marcan, tarjetas totales (amarilla=1pt, roja=2pts, convención
    de casas de apuestas) y córners.
    """
    rng = np.random.default_rng()
    lam_h, lam_a = calcular_lambdas(home_team, away_team,
                                     peso_elo=peso_elo, peso_altitud=peso_altitud,
                                     peso_arbitro=peso_arbitro)

    goles_h = rng.poisson(lam_h, n).astype(np.int32)
    goles_a = rng.poisson(lam_a, n).astype(np.int32)

    prob_home = float(np.mean(goles_h > goles_a) * 100)
    prob_draw = float(np.mean(goles_h == goles_a) * 100)
    prob_away = float(np.mean(goles_h < goles_a) * 100)

    goles_totales = goles_h + goles_a
    prob_over05 = float(np.mean(goles_totales > 0) * 100)
    prob_over15 = float(np.mean(goles_totales > 1) * 100)
    prob_over25 = float(np.mean(goles_totales > 2) * 100)
    prob_over35 = float(np.mean(goles_totales > 3) * 100)
    prob_btts = float(np.mean((goles_h > 0) & (goles_a > 0)) * 100)

    top5 = Counter(zip(goles_h.tolist(), goles_a.tolist())).most_common(5)

    # ── Córners: varias líneas, igual que el Mundial ──────────────────
    corners_esp = CORNERS_EQUIPO.get(home_team, CORNERS_DEFAULT) + CORNERS_EQUIPO.get(away_team, CORNERS_DEFAULT)
    corners_sim = rng.poisson(corners_esp, n).astype(np.int32)
    prob_corners_over65 = float(np.mean(corners_sim > 6) * 100)
    prob_corners_over75 = float(np.mean(corners_sim > 7) * 100)
    prob_corners_over85 = float(np.mean(corners_sim > 8) * 100)
    prob_corners_over95 = float(np.mean(corners_sim > 9) * 100)

    # ── Tarjetas: convención de casas de apuestas → roja = 2 amarillas ──
    amarillas_esp, rojas_esp = _tarjetas_esperadas(home_team, away_team, peso_arbitro)
    amarillas_sim = rng.poisson(amarillas_esp, n).astype(np.int32)
    rojas_sim = rng.poisson(max(rojas_esp, 0.01), n).astype(np.int32)
    tarjetas_totales_sim = amarillas_sim + 2 * rojas_sim   # roja cuenta doble
    tarjetas_totales_esp = amarillas_esp + 2 * rojas_esp
    prob_tarj_over25 = float(np.mean(tarjetas_totales_sim > 2) * 100)
    prob_tarj_over35 = float(np.mean(tarjetas_totales_sim > 3) * 100)
    prob_tarj_over45 = float(np.mean(tarjetas_totales_sim > 4) * 100)
    prob_tarj_over55 = float(np.mean(tarjetas_totales_sim > 5) * 100)

    del goles_totales, corners_sim, amarillas_sim, rojas_sim, tarjetas_totales_sim

    return {
        "prob_home": prob_home, "prob_draw": prob_draw, "prob_away": prob_away,
        "goles_home": float(np.mean(goles_h)), "goles_away": float(np.mean(goles_a)),
        "lam_home": round(lam_h, 3), "lam_away": round(lam_a, 3),
        "top5": top5,
        "prob_over05": prob_over05, "prob_over15": prob_over15,
        "prob_over25": prob_over25, "prob_over35": prob_over35,
        "prob_btts": prob_btts,
        "corners_esp": corners_esp,
        "prob_corners_over65": prob_corners_over65,
        "prob_corners_over75": prob_corners_over75,
        "prob_corners_over85": prob_corners_over85,
        "prob_corners_over95": prob_corners_over95,
        "amarillas_esp": round(amarillas_esp, 1),
        "rojas_esp": round(rojas_esp, 2),
        "tarjetas_totales_esp": round(tarjetas_totales_esp, 1),
        "prob_tarj_over25": prob_tarj_over25,
        "prob_tarj_over35": prob_tarj_over35,
        "prob_tarj_over45": prob_tarj_over45,
        "prob_tarj_over55": prob_tarj_over55,
        "arbitro": _buscar_arbitro(home_team, away_team) or "Sin asignar",
        "n_sims": n,
    }


# ─────────────────────────────────────────────────────────────────────────
# analizar_apuestas() — MISMAS REGLAS que el Mundial: umbrales dinámicos
# según qué tan "cerrado" pinta el partido, un mercado por categoría
# (para no repetir 3 líneas de córners), y nivel ALTA/MEDIA.
# ─────────────────────────────────────────────────────────────────────────
def analizar_apuestas(home_team: str, away_team: str, r: dict) -> list:
    apuestas = []

    lam_total = r["lam_home"] + r["lam_away"]
    import math as _math
    prob_00 = _math.exp(-r["lam_home"]) * _math.exp(-r["lam_away"]) * 100
    ES_PARTIDO_DEFENSIVO = prob_00 > 8 or lam_total < 2.2

    UMBRAL_RESULTADO = 55.0
    UMBRAL_DOBLE_OP = 78.0
    UMBRAL_OVER05 = min(92.0, 80.0 + prob_00 * 0.5) if prob_00 > 5 else 82.0
    UMBRAL_MERCADOS = 65.0 if ES_PARTIDO_DEFENSIVO else 70.0
    UMBRAL_TARJ = 65.0 if ES_PARTIDO_DEFENSIVO else 70.0
    UMBRAL_CORN = 65.0 if ES_PARTIDO_DEFENSIVO else 70.0

    def ap(mercado, seleccion, confianza, nota):
        apuestas.append({
            "mercado": mercado, "seleccion": seleccion,
            "confianza": confianza,
            "nivel": "ALTA" if confianza >= 78 else "MEDIA",
            "nota": nota,
        })

    pa, pd_, pb = r["prob_home"], r["prob_draw"], r["prob_away"]

    # Ganador
    if pa >= UMBRAL_RESULTADO:
        ap("Resultado (1X2)", f"✅ Gana {home_team}", pa, f"{pa:.1f}% de las simulaciones")
    if pb >= UMBRAL_RESULTADO:
        ap("Resultado (1X2)", f"✅ Gana {away_team}", pb, f"{pb:.1f}% de las simulaciones")

    # Ganador o empate (doble oportunidad)
    conf_1x = min(pa + pd_, 99)
    conf_x2 = min(pb + pd_, 99)
    if conf_1x >= UMBRAL_DOBLE_OP and pa < UMBRAL_RESULTADO:
        ap("Doble Oportunidad", f"✅ {home_team} o Empate (1X)", conf_1x, f"{pa:.1f}% + {pd_:.1f}%")
    if conf_x2 >= UMBRAL_DOBLE_OP and pb < UMBRAL_RESULTADO:
        ap("Doble Oportunidad", f"✅ {away_team} o Empate (X2)", conf_x2, f"{pb:.1f}% + {pd_:.1f}%")

    # Total de goles
    if r["prob_over05"] >= UMBRAL_OVER05:
        ap("Total Goles", "✅ Over 0.5 (al menos 1 gol)", r["prob_over05"], f"{r['prob_over05']:.1f}% de simulaciones")
    if r["prob_over15"] >= UMBRAL_MERCADOS:
        ap("Total Goles", "✅ Over 1.5 (2+ goles)", r["prob_over15"], f"{r['prob_over15']:.1f}% de simulaciones")
    if r["prob_over25"] >= UMBRAL_MERCADOS:
        ap("Total Goles", "✅ Over 2.5 (3+ goles)", r["prob_over25"], f"{r['prob_over25']:.1f}% de simulaciones")
    if r["prob_over35"] >= UMBRAL_MERCADOS:
        ap("Total Goles", "✅ Over 3.5 (4+ goles)", r["prob_over35"], f"{r['prob_over35']:.1f}% de simulaciones")
    if (100 - r["prob_over15"]) >= UMBRAL_MERCADOS:
        ap("Total Goles", "✅ Under 1.5 (0 o 1 gol)", 100 - r["prob_over15"], f"{100 - r['prob_over15']:.1f}% de simulaciones")
    if (100 - r["prob_over25"]) >= UMBRAL_MERCADOS:
        ap("Total Goles", "✅ Under 2.5 (0, 1 o 2 goles)", 100 - r["prob_over25"], f"{100 - r['prob_over25']:.1f}% de simulaciones")

    # Ambos marcan
    if r["prob_btts"] >= UMBRAL_MERCADOS:
        ap("Ambos Marcan", "✅ Sí — ambos anotan", r["prob_btts"], f"{r['prob_btts']:.1f}% de simulaciones")
    if (100 - r["prob_btts"]) >= UMBRAL_MERCADOS:
        ap("Ambos Marcan", "✅ No — al menos uno no anota", 100 - r["prob_btts"], f"{100 - r['prob_btts']:.1f}% de simulaciones")

    # Tarjetas totales (roja cuenta como 2 amarillas, convención de casas de apuestas)
    if r["prob_tarj_over25"] >= UMBRAL_TARJ:
        ap("Tarjetas", "✅ Over 2.5 tarjetas (roja=2pts)", r["prob_tarj_over25"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if r["prob_tarj_over35"] >= UMBRAL_TARJ:
        ap("Tarjetas", "✅ Over 3.5 tarjetas (roja=2pts)", r["prob_tarj_over35"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if r["prob_tarj_over45"] >= UMBRAL_TARJ:
        ap("Tarjetas", "✅ Over 4.5 tarjetas (roja=2pts)", r["prob_tarj_over45"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if (100 - r["prob_tarj_over35"]) >= UMBRAL_TARJ:
        ap("Tarjetas", "✅ Under 3.5 tarjetas (roja=2pts)", 100 - r["prob_tarj_over35"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")

    # Córners — varias líneas
    if r["prob_corners_over65"] >= UMBRAL_CORN and r["corners_esp"] >= 7:
        ap("Córners", "✅ Over 6.5 córners (7+)", r["prob_corners_over65"], f"{r['corners_esp']:.1f} esperados")
    if r["prob_corners_over75"] >= UMBRAL_CORN and r["corners_esp"] >= 8:
        ap("Córners", "✅ Over 7.5 córners (8+)", r["prob_corners_over75"], f"{r['corners_esp']:.1f} esperados")
    if r["prob_corners_over85"] >= UMBRAL_CORN:
        ap("Córners", "✅ Over 8.5 córners (9+)", r["prob_corners_over85"], f"{r['corners_esp']:.1f} esperados")
    if (100 - r["prob_corners_over85"]) >= UMBRAL_CORN:
        ap("Córners", "✅ Under 8.5 córners (máx 8)", 100 - r["prob_corners_over85"], f"{r['corners_esp']:.1f} esperados")

    apuestas.sort(key=lambda x: x["confianza"], reverse=True)

    # Un solo mercado por categoría (evita repetir 3 líneas de la misma cosa)
    filtradas = []
    categorias_vistas = set()
    for a in apuestas:
        merc = a["mercado"]
        sel = a["seleccion"].lower()
        if merc == "Tarjetas":
            cat = "tarj_over" if "over" in sel else "tarj_under"
        elif merc == "Córners":
            cat = "co_over" if "over" in sel else "co_under"
        elif merc == "Total Goles":
            cat = "goles_over" if "over" in sel else "goles_under"
        else:
            cat = merc
        if cat not in categorias_vistas:
            categorias_vistas.add(cat)
            filtradas.append(a)
    return filtradas


# ─────────────────────────────────────────────────────────────────────────
# armar_parlay() — mismo criterio que el Mundial: solo apuestas ALTA,
# máximo una por categoría (Resultado/Doble Oportunidad, Goles, Tarjetas,
# Córners, Ambos Marcan), probabilidad combinada = producto de confianzas.
# ─────────────────────────────────────────────────────────────────────────
def armar_parlay(sugerencias: list) -> dict:
    altas = [a for a in sugerencias if a["nivel"] == "ALTA"]
    if len(altas) < 2:
        return None

    seleccionadas = []
    mercados_usados = set()
    tiene_resultado = False
    for a in sorted(altas, key=lambda x: x["confianza"], reverse=True):
        merc = a["mercado"]
        if merc in ("Resultado (1X2)", "Doble Oportunidad"):
            if not tiene_resultado:
                seleccionadas.append(a)
                tiene_resultado = True
            continue
        if merc not in mercados_usados:
            seleccionadas.append(a)
            mercados_usados.add(merc)

    if len(seleccionadas) < 2:
        return None

    prob_combinada = 1.0
    for a in seleccionadas:
        prob_combinada *= a["confianza"] / 100

    return {
        "selecciones": seleccionadas,
        "texto": " + ".join(a["seleccion"].replace("✅ ", "") for a in seleccionadas),
        "prob_combinada": round(prob_combinada * 100, 1),
    }


if __name__ == "__main__":
    print("── calcular_lambdas() de ejemplo ──")
    for h, a in [("Toluca", "Tijuana"), ("America", "Guadalajara"), ("Atlante", "Tigres")]:
        lh, la = calcular_lambdas(h, a)
        print(f"  {h} (λ={lh:.2f})  vs  {a} (λ={la:.2f})")

    print("\n── simular_temporada() de ejemplo (1 corrida) ──")
    resultado = simular_temporada()
    print("Top 8 (clasifican a Liguilla):")
    for fila in resultado["tabla_final"][:8]:
        print(f"  {fila['posicion']:>2}. {fila['equipo']:<20} PTS={fila['PTS']:<3} DG={fila['DG']:<4} GF={fila['GF']}")
    print("\nCampeón simulado:", resultado["liguilla"]["campeon"])

    print("\n── simular_partido() de ejemplo (500k sims, para no tardar en la prueba) ──")
    r = simular_partido("America", "Guadalajara", n=500_000)
    print(f"  América {r['prob_home']:.1f}% - Empate {r['prob_draw']:.1f}% - Guadalajara {r['prob_away']:.1f}%")
    print(f"  Goles esperados: {r['goles_home']:.2f} - {r['goles_away']:.2f}")
    sugs = analizar_apuestas("America", "Guadalajara", r)
    print("  Apuestas sugeridas:", [(a["seleccion"], a["nivel"]) for a in sugs])
    parlay = armar_parlay(sugs)
    print("  Parlay:", parlay)
