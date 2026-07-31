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
from liga_mx_elo_update import (
    actualizar_elo, actualizar_fuerza_ataque_defensa,
    resumen_movimiento_elo, n_partidos_procesados,
)

# ─────────────────────────────────────────────────────────────────────────
# FUERZA DE ATAQUE Y DEFENSA POR EQUIPO — datos REALES del Clausura 2026
# (fuente FotMob: "goals_per_match" / "goals_conceded_per_match" — el
# promedio YA viene calculado por partido, no lo recalculamos desde
# totales porque esos totales incluyen otras competencias de la
# temporada, no solo los 17 partidos de liga — eso fue justo el bug
# que corregimos aquí).
# Atlante no jugó Primera División el Clausura 2026 (recién ascendido) —
# usa el dato real de Mazatlán como proxy (mismo criterio que ya usamos
# para CORNERS_EQUIPO y el ELO).
# ─────────────────────────────────────────────────────────────────────────
LIGA_PROMEDIO_GOLES = 1.35   # goles por equipo por partido, típico de Liga MX (~2.7 goles/partido total)

# ─────────────────────────────────────────────────────────────────────────
# CORRECCIÓN DIXON-COLES — marcadores bajos correlacionados
# En fútbol real, 0-0, 1-0, 0-1 y 1-1 ocurren un poco más seguido de lo
# que predice Poisson independiente puro (con el partido cerrado, ambos
# equipos juegan más al resultado — más cautela, menos ida y vuelta).
# Dixon & Coles (1997) corrigen justo esos 4 marcadores con un parámetro
# ρ (rho), sin tocar el resto de la distribución de goles.
#
# RHO_DIXON_COLES = -0.13 es el valor que estimaron los autores
# originales para fútbol inglés (el número más citado en la literatura
# para ligas de clubes) — lo usamos como punto de partida razonable
# mientras no tengamos suficientes partidos de Liga MX propios para
# reestimarlo por máxima verosimilitud (se necesitan ~40+ partidos con
# buena variedad de marcadores para que la reestimación sea estable).
#
# Esta corrección SOLO aplica a la distribución de GOLES (home/away) —
# no se extiende a córners ni tarjetas, que en este modelo son
# simulaciones independientes sin relación matemática con el marcador.
# ─────────────────────────────────────────────────────────────────────────
RHO_DIXON_COLES = -0.13


def _tau_dixon_coles(x: int, y: int, lam: float, mu: float, rho: float = RHO_DIXON_COLES) -> float:
    """
    Factor de corrección τ(x,y) de Dixon-Coles. Devuelve 1.0 para
    cualquier marcador fuera de {0-0, 1-0, 0-1, 1-1} — esos 4 son los
    únicos que ajusta el modelo original. lam/mu = λ_home/λ_away.
    """
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


# ─────────────────────────────────────────────────────────────────────────
# SHRINKAGE PROGRESIVO — el tope de "Forma real" y "Momentum vía Elo" no
# debería ser el mismo con 2 partidos jugados que con 15. Con pocos datos,
# un equipo que anotó 2 goles de más en su único partido podría ser pura
# suerte; con muchos partidos, la señal ya es confiable. En vez de un tope
# fijo ±8% desde el partido 1, el tope escala linealmente de 0 hasta
# TOPE_MAX_FORMA conforme el equipo acumula partidos jugados en el
# torneo, hasta llegar al tope completo en PARTIDOS_PARA_TOPE_COMPLETO.
# ─────────────────────────────────────────────────────────────────────────
TOPE_MAX_FORMA = 0.08
PARTIDOS_PARA_TOPE_COMPLETO = 10


def _tope_shrinkage(partidos_jugados: int, tope_max: float = TOPE_MAX_FORMA,
                     partidos_para_completo: int = PARTIDOS_PARA_TOPE_COMPLETO) -> float:
    """Tope dinámico (0 a tope_max) según cuántos partidos reales lleva
    jugados el equipo en el torneo — 0 partidos = 0 de tope (sin dato,
    sin ajuste), tope_max a partir de partidos_para_completo."""
    if partidos_jugados <= 0:
        return 0.0
    return tope_max * min(partidos_jugados / partidos_para_completo, 1.0)

_elo_promedio = sum(ELO.values()) / len(ELO)

FUERZA_ATAQUE = {
    "Guadalajara":        1.9,
    "Pumas UNAM":         1.8,
    "Cruz Azul":          1.8,
    "Tigres":             1.6,
    "Toluca":             1.5,
    "FC Juarez":          1.5,
    "Pachuca":            1.4,
    "America":            1.4,
    "Atletico San Luis":  1.4,
    "Leon":               1.3,
    "Atlante":            1.3,  # ⚠️ heredado de Mazatlán
    "Monterrey":          1.3,
    "Santos Laguna":      1.2,
    "Necaxa":             1.1,
    "Tijuana":            1.1,
    "Queretaro":          1.0,
    "Atlas":              0.9,
    "Puebla":             0.8,
}
FUERZA_DEFENSA = {
    "Tijuana":            1.0,
    "Toluca":             1.0,
    "Pachuca":            1.0,
    "Cruz Azul":          1.0,
    "Tigres":             1.1,
    "Guadalajara":        1.1,
    "Pumas UNAM":         1.1,
    "Queretaro":          1.2,
    "Atlas":              1.2,
    "America":            1.2,
    "Monterrey":          1.4,
    "Necaxa":             1.5,
    "Puebla":             1.5,
    "Atletico San Luis":  1.6,
    "Leon":               1.9,
    "FC Juarez":          1.9,
    "Atlante":            2.2,  # ⚠️ heredado de Mazatlán
    "Santos Laguna":      2.2,
}

# ─────────────────────────────────────────────────────────────────────────
# RECALIBRACIÓN DINÁMICA — a partir de aquí, ELO_BASE / FUERZA_ATAQUE_BASE /
# FUERZA_DEFENSA_BASE son el punto de partida "Clausura 2026" (nunca se
# tocan). ELO_ACTUALIZADO, FUERZA_ATAQUE_ACTUALIZADA y
# FUERZA_DEFENSA_ACTUALIZADA reproducen, con liga_mx_elo_update.py, cada
# partido que ya tiene resultado real en PARTIDOS — así que se recalculan
# solos cada vez que arranca la app, conforme le vas agregando jornadas
# jugadas. calcular_lambdas() usa las versiones ACTUALIZADAS.
# ─────────────────────────────────────────────────────────────────────────
ELO_BASE = dict(ELO)
FUERZA_ATAQUE_BASE = dict(FUERZA_ATAQUE)
FUERZA_DEFENSA_BASE = dict(FUERZA_DEFENSA)

ELO_ACTUALIZADO = actualizar_elo(PARTIDOS, ELO_BASE)
FUERZA_ATAQUE_ACTUALIZADA, FUERZA_DEFENSA_ACTUALIZADA = actualizar_fuerza_ataque_defensa(
    PARTIDOS, FUERZA_ATAQUE_BASE, FUERZA_DEFENSA_BASE
)
_elo_promedio_actualizado = sum(ELO_ACTUALIZADO.values()) / len(ELO_ACTUALIZADO)

# A partir de aquí, FUERZA_ATAQUE y FUERZA_DEFENSA (los nombres que usa el
# resto de este archivo) YA SON las versiones ajustadas por la forma real
# del torneo — no las estáticas de arriba. Para comparar "modelo con vs.
# sin recalibración", usa FUERZA_ATAQUE_BASE / FUERZA_DEFENSA_BASE.
FUERZA_ATAQUE = FUERZA_ATAQUE_ACTUALIZADA
FUERZA_DEFENSA = FUERZA_DEFENSA_ACTUALIZADA

# ─────────────────────────────────────────────────────────────────────────
# TARJETAS POR EQUIPO — datos reales del Clausura 2026 (fuente FotMob):
# (amarillas_totales, rojas_totales, partidos_jugados). Se usa para
# ajustar la expectativa de tarjetas combinando "carácter" del equipo
# con el promedio del árbitro asignado (ver _tarjetas_esperadas()).
# ─────────────────────────────────────────────────────────────────────────
TARJETAS_EQUIPO_LIGAMX = {
    "Santos Laguna":      (50, 5, 17),
    "Pumas UNAM":         (50, 4, 17),
    "Cruz Azul":          (49, 1, 17),
    "Guadalajara":        (49, 0, 17),
    "Tigres":             (44, 5, 17),
    "Pachuca":            (43, 7, 17),
    "Toluca":             (42, 5, 17),
    "Atlas":              (42, 4, 17),
    "Tijuana":            (42, 2, 17),
    "Queretaro":          (40, 3, 17),
    "Necaxa":             (36, 7, 17),
    "Leon":               (36, 2, 17),
    "Puebla":             (35, 6, 17),
    "Atlante":            (35, 1, 17),  # ⚠️ heredado de Mazatlán
    "FC Juarez":          (34, 3, 17),
    "Atletico San Luis":  (33, 3, 17),
    "America":            (27, 2, 17),
    "Monterrey":          (26, 1, 17),
}
_PROMEDIO_LIGA_AMARILLAS_EQUIPO = sum(v[0] / v[2] for v in TARJETAS_EQUIPO_LIGAMX.values()) / len(TARJETAS_EQUIPO_LIGAMX)

# ─────────────────────────────────────────────────────────────────────────
# FECHAS DE LEAGUES CUP POR EQUIPO — fase de grupos confirmada (4-13 de
# agosto 2026). Los 18 equipos de Liga MX participan, 3 partidos cada
# uno. Usado por _jugo_leagues_cup_reciente() para aplicar el -10% de
# fatiga cuando un equipo jugó Leagues Cup en los 7 días previos a su
# siguiente partido de Liga MX (relevante sobre todo para la Jornada 4,
# 15-17 de agosto, justo después de esta fase de grupos).
# ─────────────────────────────────────────────────────────────────────────
LEAGUES_CUP_FECHAS = {
    "America":            ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Atlante":            ["2026-08-04", "2026-08-08", "2026-08-11"],
    "Atlas":              ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Atletico San Luis":  ["2026-08-05", "2026-08-09", "2026-08-12"],
    "Cruz Azul":          ["2026-08-06", "2026-08-09", "2026-08-13"],
    "FC Juarez":          ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Guadalajara":        ["2026-08-05", "2026-08-08", "2026-08-12"],
    "Leon":               ["2026-08-05", "2026-08-08", "2026-08-12"],
    "Monterrey":          ["2026-08-05", "2026-08-08", "2026-08-12"],
    "Necaxa":             ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Pachuca":            ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Puebla":             ["2026-08-06", "2026-08-09", "2026-08-12"],
    "Pumas UNAM":         ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Queretaro":          ["2026-08-05", "2026-08-09", "2026-08-12"],
    "Santos Laguna":      ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Tigres":             ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Tijuana":            ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Toluca":             ["2026-08-05", "2026-08-08", "2026-08-12"],
}
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
                      peso_arbitro: float = 1.0,
                      peso_forma_elo: float = 1.0) -> tuple:
    """
    Calcula (lambda_home, lambda_away): la tasa esperada de goles para
    cada equipo, combinando:
      1. Ataque/Defensa — YA viene de FUERZA_ATAQUE_ACTUALIZADA /
         FUERZA_DEFENSA_ACTUALIZADA (ver liga_mx_elo_update.py): estos
         valores se recalibran solos con media móvil exponencial cada vez
         que agregas un resultado real a PARTIDOS.
      1c. Momentum vía Elo — ajuste adicional y acotado (±8%) basado en
         cuánto se movió el Elo de cada equipo (actualizar_elo(), fórmula
         Elo estándar con ventaja de local y multiplicador por goleada)
         desde el arranque del torneo. Complementa a Forma real: mientras
         Forma real mira el promedio de goles reales, este factor mira
         resultados/margen relativo a la fuerza del rival enfrentado.
      2. Forma real — goles reales anotados/recibidos en partidos ya
         jugados de este torneo (se auto-actualiza con cada resultado
         que agregues a PARTIDOS)
      3. Factor altitud (ventaja para el local en ciudades altas)
      4. Factor árbitro (promedio de tarjetas → intensidad del partido)
      5. Factor fatiga (Leagues Cup en los últimos 7 días)

    peso_elo, peso_altitud, peso_arbitro, peso_forma_elo: multiplicadores
    para ajustar cuánto pesa cada factor en el resultado final. 1.0 =
    calibración por defecto (la que ya probamos). 0.0 = el factor no
    tiene efecto. 2.0 = el doble de efecto que el calibrado. Pensados
    para conectarse directo a st.slider en la interfaz — sin tocar
    variables globales.

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

    # 1b. Forma real — ajusta con goles reales, tope progresivo (ver
    # _tope_shrinkage): empieza en 0 con pocos partidos jugados y llega a
    # TOPE_MAX_FORMA (±8%) recién a partir de PARTIDOS_PARA_TOPE_COMPLETO.
    forma = _forma_real_liga_mx()
    for equipo in (home_team, away_team):
        gf, gc, pj = forma.get(equipo, (0, 0, 0))
        if pj > 0:
            avg_gf = gf / pj
            avg_gc = gc / pj
            tope = _tope_shrinkage(pj)
            f_of = max(1.0 + min((avg_gf - LIGA_PROMEDIO_GOLES) / LIGA_PROMEDIO_GOLES, tope), 1.0 - tope)
            f_def = max(1.0 + min((avg_gc - LIGA_PROMEDIO_GOLES) / LIGA_PROMEDIO_GOLES, tope), 1.0 - tope)
            if equipo == home_team:
                lam_home *= f_of
                lam_away *= f_def
            else:
                lam_away *= f_of
                lam_home *= f_def

    # 1c. Momentum vía Elo — compara el Elo actualizado (tras reproducir
    # todos los partidos jugados) contra el Elo base de arranque de
    # temporada. Si un equipo viene rindiendo por encima de lo esperado
    # (ganó partidos cerrados que "no debía" ganar, o goleó a rivales
    # fuertes), su Elo sube y este factor empuja su λ un poco más arriba
    # — mismo tope progresivo que Forma real (ver _tope_shrinkage), por
    # equipo: cada uno usa el tope que le corresponde según SUS partidos
    # jugados, no un tope parejo para ambos.
    delta_elo_home = ELO_ACTUALIZADO.get(home_team, _elo_promedio_actualizado) - ELO_BASE.get(home_team, _elo_promedio_actualizado)
    delta_elo_away = ELO_ACTUALIZADO.get(away_team, _elo_promedio_actualizado) - ELO_BASE.get(away_team, _elo_promedio_actualizado)
    pj_home = forma.get(home_team, (0, 0, 0))[2]
    pj_away = forma.get(away_team, (0, 0, 0))[2]
    tope_elo_home = _tope_shrinkage(pj_home)
    tope_elo_away = _tope_shrinkage(pj_away)
    ajuste_elo_home = max(min(delta_elo_home / 1000, tope_elo_home), -tope_elo_home) * peso_forma_elo
    ajuste_elo_away = max(min(delta_elo_away / 1000, tope_elo_away), -tope_elo_away) * peso_forma_elo
    lam_home *= (1.0 + ajuste_elo_home)
    lam_away *= (1.0 + ajuste_elo_away)

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
    """
    Simula UN resultado (goles_home, goles_away) usando Poisson, con la
    misma corrección Dixon-Coles que simular_partido() — aquí, al ser un
    solo sorteo (no millones), se aplica por muestreo de rechazo: se
    sortea un marcador candidato y se acepta con probabilidad τ(x,y)/M
    (M = cota superior de τ). Con ρ=-0.13, M ronda ~1.1-1.3, así que casi
    siempre se acepta en el primer o segundo intento — el costo extra es
    insignificante incluso corriendo miles de temporadas completas.
    """
    if rng is None:
        rng = np.random.default_rng()
    lam_h, lam_a = calcular_lambdas(home_team, away_team,
                                     peso_elo=peso_elo,
                                     peso_altitud=peso_altitud,
                                     peso_arbitro=peso_arbitro)
    m_bound = max(1.0, 1 - lam_h * lam_a * RHO_DIXON_COLES, 1 - RHO_DIXON_COLES)
    for _ in range(200):
        goles_h = int(rng.poisson(lam_h))
        goles_a = int(rng.poisson(lam_a))
        tau = _tau_dixon_coles(goles_h, goles_a, lam_h, lam_a)
        if rng.random() < tau / m_bound:
            return goles_h, goles_a
    return goles_h, goles_a  # fallback de seguridad, en la práctica nunca se llega aquí


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


def _ordenar_tabla_con_empates(tabla: dict) -> list:
    """
    Igual que _ordenar_tabla(), pero con numeración tipo competencia:
    los equipos empatados en Pts/DG/GF comparten la misma posición y el
    siguiente lugar distinto salta el número correspondiente (1,2,2,4 —
    exactamente como se ve en la tabla oficial de Liga MX/ESPN).
    """
    filas = [{"equipo": eq, **stats} for eq, stats in tabla.items()]
    filas.sort(key=lambda f: (f["PTS"], f["DG"], f["GF"]), reverse=True)
    pos_actual = 0
    anterior = None
    for i, f in enumerate(filas, start=1):
        clave = (f["PTS"], f["DG"], f["GF"])
        if clave != anterior:
            pos_actual = i
        f["posicion"] = pos_actual
        anterior = clave
    return filas


def tabla_actual_real() -> list:
    """
    Tabla de posiciones SOLO con los partidos que ya se jugaron de
    verdad (resultado_real != None en PARTIDOS) — no mezcla nada
    simulado/proyectado. Esto es lo que debe coincidir con la tabla
    oficial de Liga MX/ESPN en cualquier momento del torneo.
    """
    tabla = _tabla_vacia()
    partidos_jugados = 0
    for local, visit, jornada, estadio, resultado, arbitro in PARTIDOS:
        if resultado is None:
            continue
        gh, ga = resultado
        _actualizar_tabla(tabla, local, visit, gh, ga)
        partidos_jugados += 1
    return _ordenar_tabla_con_empates(tabla), partidos_jugados


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


def _factor_tarjetas_equipo(equipo: str) -> float:
    """
    Qué tan por encima/debajo del promedio de liga está el ESTILO
    disciplinario del equipo (independiente del árbitro). 1.0 = promedio
    de liga. Tope [0.7, 1.4] para no sobre-ajustar con muestras chicas.
    """
    datos = TARJETAS_EQUIPO_LIGAMX.get(equipo)
    if not datos or datos[2] == 0:
        return 1.0
    am, ro, pj = datos
    return max(0.7, min(1.4, (am / pj) / _PROMEDIO_LIGA_AMARILLAS_EQUIPO))


def _tarjetas_esperadas(home_team: str, away_team: str, peso_arbitro: float = 1.0) -> tuple:
    """Devuelve (amarillas_esperadas, rojas_esperadas) para el partido,
    combinando el promedio del árbitro (70%) con el estilo disciplinario
    real de ambos equipos (30%) — mismo criterio que TARJETAS_MUNDIAL en
    tu Mundial-predictor."""
    arbitro = _buscar_arbitro(home_team, away_team)
    prom_amarillas, _n = ARBITROS_LIGA_MX.get(arbitro, (ARBITRO_DEFAULT[0], 0))
    if arbitro and arbitro in ARBITROS_LIGA_MX:
        amarillas_esp_arbitro = prom_amarillas
    else:
        desviacion = (prom_amarillas - PROMEDIO_LIGA_AMARILLAS) * peso_arbitro
        amarillas_esp_arbitro = PROMEDIO_LIGA_AMARILLAS + desviacion * 0.3

    factor_equipos = (_factor_tarjetas_equipo(home_team) + _factor_tarjetas_equipo(away_team)) / 2
    amarillas_esp = amarillas_esp_arbitro * 0.7 + (amarillas_esp_arbitro * factor_equipos) * 0.3
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

    # ── Corrección Dixon-Coles: pondera los 4 marcadores bajos ─────────
    # En vez de re-muestrear (carísimo con n=10M), se le da a cada
    # simulación un peso τ(x,y) — 1.0 para casi todas, y el factor de
    # Dixon-Coles solo para 0-0/1-0/0-1/1-1. Todas las probabilidades de
    # abajo usan np.average(..., weights=pesos_dc) en vez de np.mean(),
    # que es exactamente el estimador de Monte Carlo por importancia para
    # la distribución YA corregida — sin gastar más simulaciones.
    pesos_dc = np.ones(n, dtype=np.float64)
    m_00 = (goles_h == 0) & (goles_a == 0)
    m_10 = (goles_h == 1) & (goles_a == 0)
    m_01 = (goles_h == 0) & (goles_a == 1)
    m_11 = (goles_h == 1) & (goles_a == 1)
    pesos_dc[m_00] = max(1 - lam_h * lam_a * RHO_DIXON_COLES, 1e-6)
    pesos_dc[m_10] = max(1 + lam_a * RHO_DIXON_COLES, 1e-6)
    pesos_dc[m_01] = max(1 + lam_h * RHO_DIXON_COLES, 1e-6)
    pesos_dc[m_11] = max(1 - RHO_DIXON_COLES, 1e-6)
    del m_00, m_10, m_01, m_11

    prob_home = float(np.average(goles_h > goles_a, weights=pesos_dc) * 100)
    prob_draw = float(np.average(goles_h == goles_a, weights=pesos_dc) * 100)
    prob_away = float(np.average(goles_h < goles_a, weights=pesos_dc) * 100)

    goles_totales = goles_h + goles_a
    prob_over05 = float(np.average(goles_totales > 0, weights=pesos_dc) * 100)
    prob_over15 = float(np.average(goles_totales > 1, weights=pesos_dc) * 100)
    prob_over25 = float(np.average(goles_totales > 2, weights=pesos_dc) * 100)
    prob_over35 = float(np.average(goles_totales > 3, weights=pesos_dc) * 100)
    prob_btts = float(np.average((goles_h > 0) & (goles_a > 0), weights=pesos_dc) * 100)

    # top5 ponderado por Dixon-Coles, vectorizado (nada de loops en Python
    # sobre potencialmente 10M filas): se codifica cada marcador (gh,ga)
    # como un entero único y se suman los pesos con bincount.
    goles_h_clip = np.minimum(goles_h, 20)   # techo de seguridad, nunca se alcanza en la práctica
    goles_a_clip = np.minimum(goles_a, 20)
    claves = (goles_h_clip.astype(np.int64) * 21 + goles_a_clip.astype(np.int64))
    pesos_por_clave = np.bincount(claves, weights=pesos_dc, minlength=21 * 21)
    top5_idx = np.argsort(pesos_por_clave)[::-1][:5]
    top5 = [((int(idx // 21), int(idx % 21)), round(float(pesos_por_clave[idx]), 0))
            for idx in top5_idx if pesos_por_clave[idx] > 0]
    del goles_h_clip, goles_a_clip, claves, pesos_por_clave, top5_idx

    # ── Hándicap Asiático — probabilidad de cobertura por margen ──────
    # -1.0: cubre con diferencia >=2, empuja (reembolso) con diferencia
    # exacta de 1. -2.0: cubre con diferencia >=3, empuja con diferencia
    # exacta de 2. Se reporta la probabilidad de cobertura tal cual (sin
    # descontar el empuje del denominador) porque un empuje reembolsa el
    # stake — nunca es una pérdida, así que no le resta "certeza" a la
    # recomendación.
    diff = goles_h - goles_a
    prob_hcap_home_m10 = float(np.average(diff >= 2, weights=pesos_dc) * 100)
    prob_hcap_home_m20 = float(np.average(diff >= 3, weights=pesos_dc) * 100)
    prob_hcap_away_m10 = float(np.average(diff <= -2, weights=pesos_dc) * 100)
    prob_hcap_away_m20 = float(np.average(diff <= -3, weights=pesos_dc) * 100)
    del diff

    # ── Córners: varias líneas, igual que el Mundial ──────────────────
    corners_esp = CORNERS_EQUIPO.get(home_team, CORNERS_DEFAULT) + CORNERS_EQUIPO.get(away_team, CORNERS_DEFAULT)
    corners_sim = rng.poisson(corners_esp, n).astype(np.int32)
    prob_corners_over65 = float(np.mean(corners_sim > 6) * 100)
    prob_corners_over75 = float(np.mean(corners_sim > 7) * 100)
    prob_corners_over85 = float(np.mean(corners_sim > 8) * 100)
    prob_corners_over95 = float(np.mean(corners_sim > 9) * 100)
    prob_corners_over105 = float(np.mean(corners_sim > 10) * 100)
    prob_corners_over115 = float(np.mean(corners_sim > 11) * 100)

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
        "goles_home": float(np.average(goles_h, weights=pesos_dc)), "goles_away": float(np.average(goles_a, weights=pesos_dc)),
        "lam_home": round(lam_h, 3), "lam_away": round(lam_a, 3),
        "top5": top5,
        "prob_hcap_home_m10": prob_hcap_home_m10, "prob_hcap_home_m20": prob_hcap_home_m20,
        "prob_hcap_away_m10": prob_hcap_away_m10, "prob_hcap_away_m20": prob_hcap_away_m20,
        "prob_over05": prob_over05, "prob_over15": prob_over15,
        "prob_over25": prob_over25, "prob_over35": prob_over35,
        "prob_btts": prob_btts,
        "corners_esp": corners_esp,
        "prob_corners_over65": prob_corners_over65,
        "prob_corners_over75": prob_corners_over75,
        "prob_corners_over85": prob_corners_over85,
        "prob_corners_over95": prob_corners_over95,
        "prob_corners_over105": prob_corners_over105,
        "prob_corners_over115": prob_corners_over115,
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
    """
    Devuelve TODOS los mercados cuya probabilidad, según las simulaciones,
    llega o supera UMBRAL_RECOMENDACION (80%) — un solo criterio parejo
    para las 8 familias de mercado que soporta el modelo: Resultado (1X2),
    Doble Oportunidad, Empate Sin Apuesta (Draw No Bet), Hándicap
    Asiático, Total de Goles, Ambos Marcan, Tarjetas y Córners.

    Nota sobre Hándicap Europeo: en este modelo la probabilidad de
    "cubrir" un hándicap Europeo -1/-2 (ganar por 2+/3+) es el MISMO
    número que Hándicap Asiático -1.0/-2.0 (misma condición: diferencia de
    gol) — la única diferencia entre ambos está en qué pasa con el margen
    exacto (Asiático reembolsa, Europeo pierde), no en la confianza de la
    simulación. Por eso solo se expone Hándicap Asiático para no duplicar
    la misma señal dos veces en "apuestas sugeridas".

    NO incluye goles por mitades ni resultado al descanso (HT/FT): el
    modelo simula el partido completo con una sola λ de Poisson por
    equipo, no reparte los goles entre primer/segundo tiempo, así que no
    hay datos reales de qué tan probable es cada marcador al descanso.
    """
    apuestas = []
    UMBRAL_RECOMENDACION = 80.0

    def ap(mercado, seleccion, confianza, nota):
        apuestas.append({
            "mercado": mercado, "seleccion": seleccion,
            "confianza": confianza,
            "nivel": "ALTA",   # todo lo que entra aquí ya cumplió el 80%
            "nota": nota,
        })

    pa, pd_, pb = r["prob_home"], r["prob_draw"], r["prob_away"]

    # 1. Resultado (1X2)
    if pa >= UMBRAL_RECOMENDACION:
        ap("Resultado (1X2)", f"✅ Gana {home_team}", pa, f"{pa:.1f}% de las simulaciones")
    if pb >= UMBRAL_RECOMENDACION:
        ap("Resultado (1X2)", f"✅ Gana {away_team}", pb, f"{pb:.1f}% de las simulaciones")

    # 2. Doble Oportunidad (1X / X2)
    conf_1x = min(pa + pd_, 99)
    conf_x2 = min(pb + pd_, 99)
    if conf_1x >= UMBRAL_RECOMENDACION and pa < UMBRAL_RECOMENDACION:
        ap("Doble Oportunidad", f"✅ {home_team} o Empate (1X)", conf_1x, f"{pa:.1f}% + {pd_:.1f}%")
    if conf_x2 >= UMBRAL_RECOMENDACION and pb < UMBRAL_RECOMENDACION:
        ap("Doble Oportunidad", f"✅ {away_team} o Empate (X2)", conf_x2, f"{pb:.1f}% + {pd_:.1f}%")

    # 3. Empate Sin Apuesta (Draw No Bet) — probabilidad de ganar,
    # excluyendo del cálculo el caso "empate" (que reembolsa, no pierde).
    if (pa + pb) > 0:
        conf_dnb_home = pa / (pa + pb) * 100
        conf_dnb_away = pb / (pa + pb) * 100
        if conf_dnb_home >= UMBRAL_RECOMENDACION:
            ap("Empate Sin Apuesta", f"✅ Gana {home_team} (DNB)", conf_dnb_home,
               f"{pa:.1f}% vs {pb:.1f}% · empate ({pd_:.1f}%) reembolsa el stake")
        if conf_dnb_away >= UMBRAL_RECOMENDACION:
            ap("Empate Sin Apuesta", f"✅ Gana {away_team} (DNB)", conf_dnb_away,
               f"{pb:.1f}% vs {pa:.1f}% · empate ({pd_:.1f}%) reembolsa el stake")

    # 4. Hándicap Asiático — el favorito debe ganar por 2+ (-1.0) o 3+ (-2.0)
    if r["prob_hcap_home_m10"] >= UMBRAL_RECOMENDACION:
        ap("Hándicap Asiático", f"✅ {home_team} -1.0 (gana por 2+)", r["prob_hcap_home_m10"],
           "Empuje (reembolso) si gana por exactamente 1")
    if r["prob_hcap_home_m20"] >= UMBRAL_RECOMENDACION:
        ap("Hándicap Asiático", f"✅ {home_team} -2.0 (gana por 3+)", r["prob_hcap_home_m20"],
           "Empuje (reembolso) si gana por exactamente 2")
    if r["prob_hcap_away_m10"] >= UMBRAL_RECOMENDACION:
        ap("Hándicap Asiático", f"✅ {away_team} -1.0 (gana por 2+)", r["prob_hcap_away_m10"],
           "Empuje (reembolso) si gana por exactamente 1")
    if r["prob_hcap_away_m20"] >= UMBRAL_RECOMENDACION:
        ap("Hándicap Asiático", f"✅ {away_team} -2.0 (gana por 3+)", r["prob_hcap_away_m20"],
           "Empuje (reembolso) si gana por exactamente 2")

    # 5. Total de Goles (Over/Under)
    if r["prob_over05"] >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Over 0.5 (al menos 1 gol)", r["prob_over05"], f"{r['prob_over05']:.1f}% de simulaciones")
    if r["prob_over15"] >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Over 1.5 (2+ goles)", r["prob_over15"], f"{r['prob_over15']:.1f}% de simulaciones")
    if r["prob_over25"] >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Over 2.5 (3+ goles)", r["prob_over25"], f"{r['prob_over25']:.1f}% de simulaciones")
    if r["prob_over35"] >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Over 3.5 (4+ goles)", r["prob_over35"], f"{r['prob_over35']:.1f}% de simulaciones")
    if (100 - r["prob_over15"]) >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Under 1.5 (0 o 1 gol)", 100 - r["prob_over15"], f"{100 - r['prob_over15']:.1f}% de simulaciones")
    if (100 - r["prob_over25"]) >= UMBRAL_RECOMENDACION:
        ap("Total Goles", "✅ Under 2.5 (0, 1 o 2 goles)", 100 - r["prob_over25"], f"{100 - r['prob_over25']:.1f}% de simulaciones")

    # 6. Ambos Marcan (BTTS)
    if r["prob_btts"] >= UMBRAL_RECOMENDACION:
        ap("Ambos Marcan", "✅ Sí — ambos anotan", r["prob_btts"], f"{r['prob_btts']:.1f}% de simulaciones")
    if (100 - r["prob_btts"]) >= UMBRAL_RECOMENDACION:
        ap("Ambos Marcan", "✅ No — al menos uno no anota", 100 - r["prob_btts"], f"{100 - r['prob_btts']:.1f}% de simulaciones")

    # 7. Tarjetas totales (roja cuenta como 2 amarillas, convención de casas de apuestas)
    if r["prob_tarj_over25"] >= UMBRAL_RECOMENDACION:
        ap("Tarjetas", "✅ Over 2.5 tarjetas (roja=2pts)", r["prob_tarj_over25"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if r["prob_tarj_over35"] >= UMBRAL_RECOMENDACION:
        ap("Tarjetas", "✅ Over 3.5 tarjetas (roja=2pts)", r["prob_tarj_over35"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if r["prob_tarj_over45"] >= UMBRAL_RECOMENDACION:
        ap("Tarjetas", "✅ Over 4.5 tarjetas (roja=2pts)", r["prob_tarj_over45"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if r["prob_tarj_over55"] >= UMBRAL_RECOMENDACION:
        ap("Tarjetas", "✅ Over 5.5 tarjetas (roja=2pts)", r["prob_tarj_over55"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")
    if (100 - r["prob_tarj_over45"]) >= UMBRAL_RECOMENDACION:
        ap("Tarjetas", "✅ Under 4.5 tarjetas (roja=2pts)", 100 - r["prob_tarj_over45"], f"{r['tarjetas_totales_esp']:.1f} esperadas · árbitro {r['arbitro']}")

    # 8. Córners
    if r["prob_corners_over85"] >= UMBRAL_RECOMENDACION:
        ap("Córners", "✅ Over 8.5 córners (9+)", r["prob_corners_over85"], f"{r['corners_esp']:.1f} esperados")
    if r["prob_corners_over95"] >= UMBRAL_RECOMENDACION:
        ap("Córners", "✅ Over 9.5 córners (10+)", r["prob_corners_over95"], f"{r['corners_esp']:.1f} esperados")
    if r["prob_corners_over105"] >= UMBRAL_RECOMENDACION:
        ap("Córners", "✅ Over 10.5 córners (11+)", r["prob_corners_over105"], f"{r['corners_esp']:.1f} esperados")
    if r["prob_corners_over115"] >= UMBRAL_RECOMENDACION:
        ap("Córners", "✅ Over 11.5 córners (12+)", r["prob_corners_over115"], f"{r['corners_esp']:.1f} esperados")
    if (100 - r["prob_corners_over95"]) >= UMBRAL_RECOMENDACION:
        ap("Córners", "✅ Under 9.5 córners (máx 9)", 100 - r["prob_corners_over95"], f"{r['corners_esp']:.1f} esperados")

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
        elif merc == "Hándicap Asiático":
            # una sola línea por equipo (se queda con la de mayor confianza,
            # que tras el sort de arriba siempre es la línea más floja que
            # aún cumple el 80%, ej. -1.0 antes que -2.0 del mismo equipo)
            cat = f"hcap_{home_team}" if home_team in a["seleccion"] else f"hcap_{away_team}"
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
