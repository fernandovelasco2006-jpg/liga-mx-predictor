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


def calcular_lambdas(home_team: str, away_team: str) -> tuple:
    """
    Calcula (lambda_home, lambda_away): la tasa esperada de goles para
    cada equipo, combinando:
      1. Ataque/Defensa (relativo al ELO, ver nota de PLACEHOLDER arriba)
      2. Factor altitud (ventaja para el local en ciudades altas)
      3. Factor árbitro (promedio de tarjetas → intensidad del partido)
      4. Factor fatiga (Leagues Cup en los últimos 7 días)

    Devuelve (lambda_home, lambda_away) listos para simular goles con
    una distribución de Poisson.
    """
    # 1. Ataque / Defensa ────────────────────────────────────────────
    ataque_home = FUERZA_ATAQUE.get(home_team, LIGA_PROMEDIO_GOLES)
    defensa_home = FUERZA_DEFENSA.get(home_team, LIGA_PROMEDIO_GOLES)
    ataque_away = FUERZA_ATAQUE.get(away_team, LIGA_PROMEDIO_GOLES)
    defensa_away = FUERZA_DEFENSA.get(away_team, LIGA_PROMEDIO_GOLES)

    # Modelo clásico tipo Dixon-Coles: goles esperados del local
    # dependen de SU ataque y de la defensa del VISITANTE (y viceversa).
    lam_home = (ataque_home / LIGA_PROMEDIO_GOLES) * (defensa_away / LIGA_PROMEDIO_GOLES) * LIGA_PROMEDIO_GOLES
    lam_away = (ataque_away / LIGA_PROMEDIO_GOLES) * (defensa_home / LIGA_PROMEDIO_GOLES) * LIGA_PROMEDIO_GOLES

    # Ventaja de localía estándar (típico ~10-15% en fútbol de liga)
    lam_home *= 1.12

    # 2. Factor altitud ───────────────────────────────────────────────
    alt_local = ALTITUD_EQUIPO.get(home_team)
    if alt_local is not None and alt_local >= ALTITUD_UMBRAL:
        if away_team not in EQUIPOS_ACLIMATADOS_ALTURA:
            # el visitante no está acostumbrado a la altura → el local
            # se beneficia más de lo normal
            lam_home += BONUS_ALTITUD_LOCAL
        else:
            # ambos equipos están acostumbrados a la altura → bonus reducido
            lam_home += BONUS_ALTITUD_LOCAL * 0.3

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
    # tope de +-10% para no sobre-ajustar con muestras chicas
    factor_arbitro = 1.0 - max(min(desviacion * 0.015, 0.10), -0.10)
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
def _jugar_partido(home_team: str, away_team: str, rng=None) -> tuple:
    """Simula UN resultado (goles_home, goles_away) usando Poisson."""
    if rng is None:
        rng = np.random.default_rng()
    lam_h, lam_a = calcular_lambdas(home_team, away_team)
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


def _jugar_serie_ida_vuelta(equipo_A: str, equipo_B: str, seed_A: int, seed_B: int, rng=None) -> dict:
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

    gh1, ga1 = _jugar_partido(peor, mejor, rng)     # ida: local el peor posicionado
    gh2, ga2 = _jugar_partido(mejor, peor, rng)     # vuelta: local el mejor posicionado

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


def simular_temporada(rng=None) -> dict:
    """
    Simula la fase regular completa (17 jornadas) + Liguilla completa.

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

    tabla = _tabla_vacia()
    for home, away, jornada, estadio, resultado_real, arbitro in PARTIDOS:
        if resultado_real is not None:
            # partido ya jugado en la vida real → usa el resultado real
            gh, ga = resultado_real
        else:
            gh, ga = _jugar_partido(home, away, rng)
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
        _jugar_serie_ida_vuelta(a, b, seed[a], seed[b], rng)
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
        _jugar_serie_ida_vuelta(a, b, seed[a], seed[b], rng)
        for a, b in pares_semis
    ]

    # ── Final ───────────────────────────────────────────────────────
    finalistas = [s["ganador"] for s in semis]
    final = _jugar_serie_ida_vuelta(finalistas[0], finalistas[1],
                                     seed[finalistas[0]], seed[finalistas[1]], rng)

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
def simular_temporada_montecarlo(n: int = 1000) -> dict:
    rng = np.random.default_rng()
    conteo_liguilla = defaultdict(int)
    conteo_campeon = defaultdict(int)
    suma_posicion = defaultdict(int)

    for _ in range(n):
        resultado = simular_temporada(rng)
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
# Prueba rápida
# ─────────────────────────────────────────────────────────────────────────
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
