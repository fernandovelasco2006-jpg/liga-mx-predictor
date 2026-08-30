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
    FUERZA_ATAQUE_LOCAL, FUERZA_ATAQUE_VISITA, FUERZA_DEFENSA_LOCAL, FUERZA_DEFENSA_VISITA,
)
from liga_mx_elo_update import (
    actualizar_elo, actualizar_fuerza_ataque_defensa,
    resumen_movimiento_elo, n_partidos_procesados,
)

# Import opcional — liga_mx_cuotas.py depende de requests y de tener una
# API key de The Odds API configurada en algún lado; si el módulo no
# está presente (entorno de pruebas, o el usuario aún no lo agregó al
# repo), analizar_apuestas() sigue funcionando exactamente igual, solo
# que sin la sección de value_bet.
try:
    from liga_mx_cuotas import calcular_value_bet
except ImportError:
    def calcular_value_bet(prob_modelo_pct, cuota_decimal):
        return {"ev_pct": None, "prob_implicita_pct": None, "tiene_valor": False}

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
LIGA_PROMEDIO_GOLES = 1.3693  # exacto: suma GF de los 18 equipos / (18×17) del Clausura 2026 — antes 1.35 (aproximado)

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


# ─────────────────────────────────────────────────────────────────────────
# SESGO LOCAL/VISITA — cuánto mejor/peor rinde un equipo jugando en casa
# vs. de visita, respecto a SU PROPIO promedio de temporada (Clausura
# 2026). Viene de una fuente externa verificada contra los totales
# oficiales (ver FUERZA_ATAQUE_LOCAL/VISITA en el skeleton), pero con
# solo 8-9 partidos por categoría es una muestra chica — se topa a ±20%
# para no sobre-corregir con ruido.
# ─────────────────────────────────────────────────────────────────────────
TOPE_SESGO_LOCAL_VISITA = 0.20


def _razon_capada(valor: float, base: float, tope: float = TOPE_SESGO_LOCAL_VISITA) -> float:
    """valor/base, acotado a [1-tope, 1+tope]. Si falta cualquiera de los
    dos datos, devuelve 1.0 (sin ajuste)."""
    if not valor or not base or base <= 0:
        return 1.0
    razon = valor / base
    return max(1.0 - tope, min(1.0 + tope, razon))

_elo_promedio = sum(ELO.values()) / len(ELO)

FUERZA_ATAQUE = {
    # Recalibrado con la tabla exacta del Clausura 2026 (17 partidos,
    # gf/pj — la tabla cuadra perfectamente con W-E-P y puntos de cada
    # equipo, así que se usa tal cual en vez de la estimación anterior).
    "Pumas UNAM":         2.00,  # antes 1.8 — GF real más alto de lo estimado
    "Guadalajara":        1.94,
    "Cruz Azul":          1.82,
    "Tigres":             1.65,
    "Toluca":             1.65,
    "FC Juarez":          1.53,
    "Pachuca":            1.47,
    "Atletico San Luis":  1.41,
    "Leon":               1.29,
    "Atlante":            1.29,  # ⚠️ heredado de Mazatlán
    "Monterrey":          1.29,
    "America":            1.18,  # antes 1.4 — GF real bastante más bajo de lo estimado
    "Santos Laguna":      1.18,
    "Necaxa":             1.12,
    "Tijuana":            1.12,
    "Queretaro":          1.00,
    "Atlas":              0.94,
    "Puebla":             0.76,
}
FUERZA_DEFENSA = {
    # Mismo criterio: gc/pj exacto de la tabla del Clausura 2026.
    "Toluca":             0.94,
    "Guadalajara":        1.00,  # antes 1.1
    "Pumas UNAM":         1.00,  # antes 1.1
    "America":            1.00,  # antes 1.2 — defensa real mejor de lo estimado
    "Tijuana":            1.00,
    "Cruz Azul":          1.06,
    "Tigres":             1.06,
    "Atlas":              1.06,  # antes 1.2 — defensa real mejor de lo estimado
    "Pachuca":            1.12,  # antes 1.0 — defensa real algo peor de lo estimado
    "Queretaro":          1.24,
    "Monterrey":          1.41,
    "Necaxa":             1.47,
    "Puebla":             1.53,
    "Atletico San Luis":  1.59,
    "Leon":               1.88,
    "FC Juarez":          1.88,
    "Atlante":            2.18,  # ⚠️ heredado de Mazatlán
    "Santos Laguna":      2.24,
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
# TARJETAS POR EQUIPO — Clausura 2026 (fuente FotMob, 17 PJ, ver arriba)
# vs. Apertura 2026 EN VIVO (fuente ligamx.net, tabla oficial de
# Tarjetas Amarillas/Rojas por Club).
#
# A diferencia de FUERZA_ATAQUE/FUERZA_DEFENSA (que se recalibran solas
# vía liga_mx_elo_update.py leyendo PARTIDOS), este dato NO tiene fuente
# automática en el modelo — ligamx.net no expone una API pública, así
# que se actualiza pegando la tabla manualmente aquí cada cierto número
# de jornadas. _factor_tarjetas_equipo() mezcla ambos con el MISMO
# shrinkage progresivo que usa _tope_shrinkage() para Forma real/Elo:
# con pocos PJ del Apertura pesa más el Clausura (dato robusto, 17 PJ),
# y conforme se acumulan partidos el Apertura gana peso hasta dominar
# por completo a partir de PARTIDOS_PARA_TOPE_COMPLETO.
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

# Apertura 2026 EN VIVO — (amarillas_totales, rojas_totales, partidos_jugados)
# Fuente: ligamx.net, tabla "Tarjetas Amarillas"/"Tarjetas Rojas" por
# club, consultada tras la Jornada 5 (5 PJ para todos los equipos).
# ACTUALIZAR estos números (y el "5" del comentario de arriba) cada vez
# que se pegue una tabla nueva de ligamx.net.
TARJETAS_EQUIPO_APERTURA = {
    "Atlas":              (21, 3, 5),
    "Pachuca":            (11, 2, 5),
    "FC Juarez":          (10, 0, 5),
    "Leon":               (10, 3, 5),
    "Necaxa":             (10, 2, 5),
    "Tigres":             (10, 1, 5),
    "America":            (9, 1, 5),
    "Cruz Azul":          (9, 0, 5),
    "Monterrey":          (7, 2, 5),
    "Tijuana":            (7, 0, 5),
    "Toluca":             (7, 1, 5),
    "Guadalajara":        (6, 1, 5),
    "Pumas UNAM":         (6, 0, 5),
    "Atletico San Luis":  (5, 1, 5),
    "Santos Laguna":      (5, 0, 5),
    "Puebla":             (4, 1, 5),
    # Atlante y Queretaro no traían conteo propio en la tabla pegada (0
    # tarjetas registradas) — se dejan fuera a propósito para que
    # _factor_tarjetas_equipo() caiga de vuelta al dato de Clausura sin
    # mezclar un "0 tarjetas" engañoso.
}


def _factor_tarjetas_equipo(equipo: str) -> float:
    """
    Qué tan por encima/debajo del promedio de liga está el ESTILO
    disciplinario del equipo (independiente del árbitro). 1.0 = promedio
    de liga. Tope [0.7, 1.4] para no sobre-ajustar con muestras chicas.

    Mezcla Clausura 2026 (base robusta, 17 PJ) con Apertura 2026 EN VIVO
    (TARJETAS_EQUIPO_APERTURA) usando el mismo shrinkage progresivo que
    _tope_shrinkage(): con 0 PJ del Apertura, 100% Clausura; a partir de
    PARTIDOS_PARA_TOPE_COMPLETO PJ del Apertura, 100% Apertura.
    """
    datos_clausura = TARJETAS_EQUIPO_LIGAMX.get(equipo)
    datos_apertura = TARJETAS_EQUIPO_APERTURA.get(equipo)

    prom_clausura = None
    if datos_clausura and datos_clausura[2] > 0:
        am_c, _ro_c, pj_c = datos_clausura
        prom_clausura = am_c / pj_c

    prom_apertura = None
    pj_apertura = 0
    if datos_apertura and datos_apertura[2] > 0:
        am_a, _ro_a, pj_apertura = datos_apertura
        prom_apertura = am_a / pj_apertura

    if prom_clausura is None and prom_apertura is None:
        return 1.0
    if prom_clausura is None:
        promedio_mezclado = prom_apertura
    elif prom_apertura is None:
        promedio_mezclado = prom_clausura
    else:
        peso_apertura = min(pj_apertura / PARTIDOS_PARA_TOPE_COMPLETO, 1.0)
        promedio_mezclado = (1 - peso_apertura) * prom_clausura + peso_apertura * prom_apertura

    return max(0.7, min(1.4, promedio_mezclado / _PROMEDIO_LIGA_AMARILLAS_EQUIPO))

# ─────────────────────────────────────────────────────────────────────────
# FECHAS DE LEAGUES CUP POR EQUIPO — fase de grupos confirmada (4-13 de
# agosto 2026). Los 18 equipos de Liga MX participan, 3 partidos cada
# uno. Usado por _jugo_leagues_cup_reciente() para aplicar el -10% de
# fatiga cuando un equipo jugó Leagues Cup en los 7 días previos a su
# siguiente partido de Liga MX (relevante sobre todo para la Jornada 4,
# 15-17 de agosto, justo después de esta fase de grupos).
#
# CUARTOS DE FINAL (25-27 agosto): solo 4 equipos de Liga MX avanzaron —
# América (vs Columbus Crew), León (vs Real Salt Lake), Monterrey (vs
# Chicago Fire FC) y Toluca (vs Austin FC). La hora exacta de cada
# partido de cuartos todavía no está confirmada, así que se agregaron
# las 3 fechas posibles (25/26/27) como candidatas — no afecta la
# precisión del cálculo de fatiga, solo amplía un poco la ventana.
# Si alguno de estos 4 avanza a semis (1-2 sep) o final (6 sep), hay que
# agregar esas fechas también cuando se confirme.
# ─────────────────────────────────────────────────────────────────────────
LEAGUES_CUP_FECHAS = {
    "America":            ["2026-08-06", "2026-08-09", "2026-08-13",
                            "2026-08-25", "2026-08-26", "2026-08-27"],  # + cuartos vs Columbus Crew (fecha exacta TBD)
    "Atlante":            ["2026-08-04", "2026-08-08", "2026-08-11"],
    "Atlas":              ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Atletico San Luis":  ["2026-08-05", "2026-08-09", "2026-08-12"],
    "Cruz Azul":          ["2026-08-06", "2026-08-09", "2026-08-13"],
    "FC Juarez":          ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Guadalajara":        ["2026-08-05", "2026-08-08", "2026-08-12"],
    "Leon":               ["2026-08-05", "2026-08-08", "2026-08-12",
                            "2026-08-25", "2026-08-26", "2026-08-27"],  # + cuartos vs Real Salt Lake (fecha exacta TBD)
    "Monterrey":          ["2026-08-05", "2026-08-08", "2026-08-12",
                            "2026-08-25", "2026-08-26", "2026-08-27"],  # + cuartos vs Chicago Fire FC (fecha exacta TBD)
    "Necaxa":             ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Pachuca":            ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Puebla":             ["2026-08-06", "2026-08-09", "2026-08-12"],
    "Pumas UNAM":         ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Queretaro":          ["2026-08-05", "2026-08-09", "2026-08-12"],
    "Santos Laguna":      ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Tigres":             ["2026-08-04", "2026-08-07", "2026-08-11"],
    "Tijuana":            ["2026-08-06", "2026-08-09", "2026-08-13"],
    "Toluca":             ["2026-08-05", "2026-08-08", "2026-08-12",
                            "2026-08-25", "2026-08-26", "2026-08-27"],  # + cuartos vs Austin FC (fecha exacta TBD)
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
                      peso_forma_elo: float = 1.0,
                      factor_clima: float = 1.0,
                      peso_local_visita: float = 1.0,
                      sesgo_por_equipo: dict = None) -> tuple:
    """
    Calcula (lambda_home, lambda_away): la tasa esperada de goles para
    cada equipo, combinando:
      1. Ataque/Defensa — YA viene de FUERZA_ATAQUE_ACTUALIZADA /
         FUERZA_DEFENSA_ACTUALIZADA (ver liga_mx_elo_update.py): estos
         valores se recalibran solos con media móvil exponencial cada vez
         que agregas un resultado real a PARTIDOS.
      1a. Sesgo local/visita — ajuste acotado (±20%) según qué tan mejor/
         peor rinde CADA equipo jugando en casa vs. de visita, respecto a
         su propio promedio de temporada (Clausura 2026, verificado contra
         los totales oficiales). El local usa su sesgo de local, el
         visitante el suyo de visitante — nunca se mezclan.
      1c. Momentum vía Elo — ajuste adicional y acotado (±8%) basado en
         cuánto se movió el Elo de cada equipo (actualizar_elo(), fórmula
         Elo estándar con ventaja de local y multiplicador por goleada)
         desde el arranque del torneo. Complementa a Forma real: mientras
         Forma real mira el promedio de goles reales, este factor mira
         resultados/margen relativo a la fuerza del rival enfrentado.
      1d. Corrección de sesgo del propio modelo (retroalimentación) —
         ajuste acotado (±15%, ver liga_mx_supabase.calcular_sesgo_por_
         equipo()) basado en cuánto se ha equivocado ESTE modelo en
         particular prediciendo a este equipo, comparando goles_esp
         guardados en predicciones_ligamx contra los goles reales que
         anotó — separado por local/visita. Solo se aplica si el
         llamador pasa sesgo_por_equipo (ver parámetro) Y ese equipo ya
         acumuló el mínimo de partidos evaluados (8 por defecto); si no
         hay dato, este paso no hace nada (factor 1.0, sin sorpresas).
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

    sesgo_por_equipo: diccionario opcional, salida directa de
    liga_mx_supabase.calcular_sesgo_por_equipo(historial_predicciones).
    Si se omite (None, el default), este paso simplemente no se aplica
    — así calcular_lambdas() sigue funcionando exactamente igual que
    antes para quien no le pase este dato (retrocompatible, sin romper
    ninguna llamada existente en simular_partido()/simular_temporada()).

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

    # 1a. Sesgo local/visita — el equipo LOCAL usa su propio sesgo "jugando
    # en casa", el VISITANTE usa su propio sesgo "jugando fuera". No se
    # mezclan (el sesgo de local de un equipo no le aplica cuando visita).
    razon_ataque_home = _razon_capada(FUERZA_ATAQUE_LOCAL.get(home_team), FUERZA_ATAQUE_BASE.get(home_team))
    razon_defensa_home = _razon_capada(FUERZA_DEFENSA_LOCAL.get(home_team), FUERZA_DEFENSA_BASE.get(home_team))
    razon_ataque_away = _razon_capada(FUERZA_ATAQUE_VISITA.get(away_team), FUERZA_ATAQUE_BASE.get(away_team))
    razon_defensa_away = _razon_capada(FUERZA_DEFENSA_VISITA.get(away_team), FUERZA_DEFENSA_BASE.get(away_team))
    ataque_home *= 1.0 + peso_local_visita * (razon_ataque_home - 1.0)
    defensa_home *= 1.0 + peso_local_visita * (razon_defensa_home - 1.0)
    ataque_away *= 1.0 + peso_local_visita * (razon_ataque_away - 1.0)
    defensa_away *= 1.0 + peso_local_visita * (razon_defensa_away - 1.0)

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

    # 1d. Corrección de sesgo del propio modelo (retroalimentación) —
    # ver liga_mx_supabase.calcular_sesgo_por_equipo(). Solo actúa si el
    # llamador pasó el diccionario Y el equipo/rol ya tiene suficiente
    # muestra evaluada (calcular_sesgo_por_equipo() ya filtra eso, así
    # que aquí basta con comprobar que la clave exista).
    if sesgo_por_equipo:
        sesgo_home = sesgo_por_equipo.get(home_team, {})
        sesgo_away = sesgo_por_equipo.get(away_team, {})
        if "factor_ataque_local" in sesgo_home:
            lam_home *= sesgo_home["factor_ataque_local"]
        if "factor_ataque_visita" in sesgo_away:
            lam_away *= sesgo_away["factor_ataque_visita"]

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

    # 5. Clima — factor pequeño y simétrico (afecta al partido completo,
    # no a un solo equipo). Viene precalculado de liga_mx_clima.factor_clima()
    # y por defecto es 1.0 (sin ajuste) si no hay API key de clima
    # configurada o no se pudo consultar.
    lam_home *= factor_clima
    lam_away *= factor_clima

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
from liga_mx_predictor_skeleton import (
    CORNERS_EQUIPO, CORNERS_DEFAULT, CORNERS_EQUIPO_CONTRA, CORNERS_DEFAULT_CONTRA,
)

PROMEDIO_LIGA_AMARILLAS = 4.3
PROMEDIO_LIGA_ROJAS = 0.41   # real: 7 rojas / 17 partidos con dato — antes 0.15 (placeholder sin datos)



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
                     peso_arbitro: float = 1.0, factor_clima: float = 1.0,
                     sesgo_por_equipo: dict = None) -> dict:
    """
    Corre N simulaciones Monte Carlo de UN partido (10,000,000 por
    defecto, igual que en tu predictor del Mundial) y agrega
    probabilidades por mercado: 1X2, doble oportunidad, total de goles,
    ambos marcan, tarjetas totales (amarilla=1pt, roja=2pts, convención
    de casas de apuestas) y córners.

    sesgo_por_equipo: opcional, se pasa tal cual a calcular_lambdas()
    (ver ahí el detalle) — normalmente la salida de
    liga_mx_supabase.calcular_sesgo_por_equipo(historial_predicciones).
    Si se omite, el modelo funciona exactamente igual que antes.
    """
    rng = np.random.default_rng()
    lam_h, lam_a = calcular_lambdas(home_team, away_team,
                                     peso_elo=peso_elo, peso_altitud=peso_altitud,
                                     peso_arbitro=peso_arbitro, factor_clima=factor_clima,
                                     sesgo_por_equipo=sesgo_por_equipo)

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
    # Córners: ataque × defensa (mismo criterio que los goles) en vez de
    # solo sumar los córners "a favor" de cada equipo — ahora sí se
    # considera que un equipo con defensa sólida le baja los córners al
    # rival, y uno flojo se los sube.
    co_favor_home = CORNERS_EQUIPO.get(home_team, CORNERS_DEFAULT)
    co_favor_away = CORNERS_EQUIPO.get(away_team, CORNERS_DEFAULT)
    co_contra_home = CORNERS_EQUIPO_CONTRA.get(home_team, CORNERS_DEFAULT_CONTRA)
    co_contra_away = CORNERS_EQUIPO_CONTRA.get(away_team, CORNERS_DEFAULT_CONTRA)
    corners_esp_home = co_favor_home * (co_contra_away / CORNERS_DEFAULT_CONTRA)
    corners_esp_away = co_favor_away * (co_contra_home / CORNERS_DEFAULT_CONTRA)
    corners_esp = corners_esp_home + corners_esp_away
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
# UMBRAL DINÁMICO POR CONFIANZA DE MUESTRA — el modelo exige más certeza
# cuando tiene poca evidencia real del torneo actual (jornada 1-2,
# apoyándose solo en datos heredados del Clausura 2026) y se relaja
# conforme se acumulan partidos jugados y la Forma real / Momentum Elo
# (ver calcular_lambdas()) empiezan a pesar de verdad.
#
# Mismo principio que _tope_shrinkage(): interpolación lineal entre un
# piso y un techo, según PJ del torneo. Aquí va en sentido inverso (más
# PJ = umbral MÁS BAJO) porque más partidos jugados = más confianza en
# el modelo, no menos.
#
# UMBRAL_MAX_RECOMENDACION (90%) = con 0 partidos jugados del Apertura
# 2026, toda la fuerza del cálculo viene de datos heredados (Clausura
# 2026 + Elo base) — exige el mayor margen de error.
# UMBRAL_MIN_RECOMENDACION (80%) = a partir de PJ_PARA_UMBRAL_MIN
# partidos jugados por AMBOS equipos, la Forma real ya alcanzó su tope
# completo de ajuste (mismo umbral que usa _tope_shrinkage para llegar a
# TOPE_MAX_FORMA) — el modelo ya opera con evidencia sólida del torneo.
# ─────────────────────────────────────────────────────────────────────────
UMBRAL_MAX_RECOMENDACION = 90.0
UMBRAL_MIN_RECOMENDACION = 80.0
PJ_PARA_UMBRAL_MIN = 10  # mismo valor que PARTIDOS_PARA_TOPE_COMPLETO


def _umbral_dinamico(home_team: str, away_team: str) -> float:
    """
    Umbral de confianza requerido para que una apuesta se recomiende,
    interpolado linealmente entre UMBRAL_MAX_RECOMENDACION (0 PJ) y
    UMBRAL_MIN_RECOMENDACION (PJ_PARA_UMBRAL_MIN+ PJ), usando el PROMEDIO
    de partidos jugados en el torneo por ambos equipos — si un equipo
    lleva 2 PJ y el otro 5, se interpola con 3.5.
    """
    forma = _forma_real_liga_mx()
    pj_home = forma.get(home_team, (0, 0, 0))[2]
    pj_away = forma.get(away_team, (0, 0, 0))[2]
    pj_promedio = (pj_home + pj_away) / 2.0

    fraccion = min(pj_promedio / PJ_PARA_UMBRAL_MIN, 1.0)
    return UMBRAL_MAX_RECOMENDACION - fraccion * (UMBRAL_MAX_RECOMENDACION - UMBRAL_MIN_RECOMENDACION)


# ─────────────────────────────────────────────────────────────────────────
# analizar_apuestas() — umbral dinámico (ver _umbral_dinamico()) y SIN
# deduplicar por categoría: se muestran TODAS las líneas que cumplen el
# umbral (ej. Over 0.5 + Over 1.5 + Over 2.5 a la vez, si las 3 pasan).
# ─────────────────────────────────────────────────────────────────────────
def analizar_apuestas(home_team: str, away_team: str, r: dict, mercados_suspendidos: frozenset = frozenset(),
                       cuotas: dict = None) -> list:
    """
    Devuelve TODOS los mercados cuya probabilidad, según las simulaciones,
    llega o supera el umbral dinámico calculado por _umbral_dinamico()
    (80%-90% según cuántos partidos reales del Apertura 2026 ya jugaron
    ambos equipos) — para las 8 familias de mercado que soporta el
    modelo: Resultado (1X2), Doble Oportunidad, Empate Sin Apuesta (Draw
    No Bet), Hándicap Asiático, Total de Goles, Ambos Marcan, Tarjetas y
    Córners.

    IMPORTANTE — sin deduplicar por categoría: se devuelven TODAS las
    líneas que cumplen el umbral, no solo una por categoría, para no
    ocultar señales fuertes que sí tienen la confianza requerida.

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

    mercados_suspendidos: set con nombres de mercado (ej. {"Total Goles"})
    que se excluyen del resultado aunque hayan cumplido el umbral — viene
    de liga_mx_supabase.calcular_mercados_suspendidos(), la
    retroalimentación automática que apaga temporalmente un mercado si su
    acierto real viene rindiendo muy por debajo de lo que promete.

    cuotas: opcional, dict de cuotas reales para ESTE partido (formato
    {"home": float, "draw": float, "away": float, "casa": str} — ver
    liga_mx_cuotas.obtener_cuotas_jornada()). Si se pasa, se calcula
    Value Betting (liga_mx_cuotas.calcular_value_bet()) SOLO para el
    mercado Resultado (1X2): The Odds API en el plan gratis únicamente
    trae el mercado h2h para Liga MX (spreads/totals están limitados a
    deportes de EE.UU. en su documentación), así que no hay cuota real
    con la que comparar Total Goles, Tarjetas, Córners, etc. — esos
    mercados siguen funcionando exactamente igual que sin este parámetro.
    Si se omite (None, default), el comportamiento es idéntico al de
    antes de agregar value betting — retrocompatible.

    DECISIÓN DE DISEÑO explícita: el value bet de 1X2 SOLO se calcula
    sobre selecciones que YA superaron UMBRAL_RECOMENDACION (80-90%
    dinámico) — no se expone un mercado aparte de "underdogs con valor"
    para resultados poco probables aunque tengan EV positivo (ej. 30% de
    probabilidad con una cuota que pague mucho). El value bet funciona
    como una validación adicional sobre las recomendaciones de alta
    confianza que el modelo ya hace, no como un criterio independiente
    de selección — así que una apuesta de 1X2 con EV negativo puede
    seguir apareciendo en "Apuestas sugeridas" si su confianza superó el
    umbral; el campo "value_bet" simplemente informa si, además de ser
    probable, también es un buen negocio contra la cuota real.
    """
    apuestas = []
    UMBRAL_RECOMENDACION = _umbral_dinamico(home_team, away_team)

    def ap(mercado, seleccion, confianza, nota, cuota_decimal=None):
        entrada = {
            "mercado": mercado, "seleccion": seleccion,
            "confianza": confianza,
            "nivel": "ALTA",   # todo lo que entra aquí ya cumplió el umbral
            "nota": nota,
            "umbral_aplicado": round(UMBRAL_RECOMENDACION, 1),
        }
        if cuota_decimal is not None:
            entrada["value_bet"] = calcular_value_bet(confianza, cuota_decimal)
        apuestas.append(entrada)

    pa, pd_, pb = r["prob_home"], r["prob_draw"], r["prob_away"]

    # 1. Resultado (1X2) — único mercado con value betting (ver docstring)
    cuota_home = cuotas.get("home") if cuotas else None
    cuota_away = cuotas.get("away") if cuotas else None
    if pa >= UMBRAL_RECOMENDACION:
        ap("Resultado (1X2)", f"✅ Gana {home_team}", pa, f"{pa:.1f}% de las simulaciones", cuota_decimal=cuota_home)
    if pb >= UMBRAL_RECOMENDACION:
        ap("Resultado (1X2)", f"✅ Gana {away_team}", pb, f"{pb:.1f}% de las simulaciones", cuota_decimal=cuota_away)

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

    # Una sola línea por RUBRO/categoría (Resultado, Doble Oportunidad,
    # Total Goles, Ambos Marcan, Hándicap, Tarjetas, Córners) — evita
    # mostrar "Over 0.5" y "Over 1.5" a la vez dentro de Total Goles,
    # pero SÍ permite que salgan simultáneamente apuestas de rubros
    # distintos (ej. una de Total Goles + una de Tarjetas + una de
    # Córners), siempre que cada una cumpla el umbral dinámico.
    #
    # Dentro de cada categoría se conserva la de MAYOR confianza (la
    # línea más "segura"/menos específica que sostiene la categoría) —
    # ej. entre Over 0.5 al 95% y Over 1.5 al 85.5%, se muestra Over 0.5.
    # Ojo: para Under es al revés en términos de "línea", pero el
    # criterio se mantiene igual (mayor % de confianza gana), porque el
    # número de confianza ya captura qué tan sólida es cada selección —
    # no hace falta lógica especial por dirección Over/Under.
    mejor_por_categoria = {}
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
            cat = f"hcap_{home_team}" if home_team in a["seleccion"] else f"hcap_{away_team}"
        else:
            cat = merc
        if cat not in mejor_por_categoria or a["confianza"] > mejor_por_categoria[cat]["confianza"]:
            mejor_por_categoria[cat] = a

    filtradas = sorted(mejor_por_categoria.values(), key=lambda x: x["confianza"], reverse=True)
    if mercados_suspendidos:
        filtradas = [a for a in filtradas if a["mercado"] not in mercados_suspendidos]
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


# ─────────────────────────────────────────────────────────────────────────
# detectar_jornada_actual() + simular_jornada_completa() — soporte para
# el botón "Simular Jornada" de la interfaz: detecta automáticamente cuál
# es la jornada pendiente más próxima (según los resultados que ya están
# cargados en PARTIDOS, no según la fecha de hoy — evita errores si algún
# partido se pospuso o adelantó) y corre simular_partido() +
# analizar_apuestas() para todos sus partidos de un jalón.
# ─────────────────────────────────────────────────────────────────────────
def detectar_jornada_actual() -> int:
    """
    Devuelve el número de la primera jornada que todavía tiene al menos
    un partido con resultado=None en PARTIDOS — es decir, la próxima
    jornada por jugar/simular. Si todos los partidos ya tienen
    resultado (temporada terminada), devuelve None.
    """
    jornadas_pendientes = sorted({
        jornada for local, visit, jornada, estadio, resultado, arbitro in PARTIDOS
        if resultado is None
    })
    return jornadas_pendientes[0] if jornadas_pendientes else None


def partidos_de_jornada(jornada: int) -> list:
    """Devuelve las tuplas de PARTIDOS que pertenecen a esa jornada,
    en el mismo orden en que aparecen en PARTIDOS."""
    return [p for p in PARTIDOS if p[2] == jornada]


def simular_jornada_completa(jornada: int = None, n: int = 2_000_000,
                              peso_elo: float = 1.0, peso_altitud: float = 1.0,
                              peso_arbitro: float = 1.0, factor_clima: float = 1.0,
                              mercados_suspendidos: frozenset = frozenset(),
                              sesgo_por_equipo: dict = None) -> dict:
    """
    Corre simular_partido() + analizar_apuestas() para TODOS los
    partidos de una jornada (por defecto, la detectada automáticamente
    por detectar_jornada_actual() — la próxima jornada pendiente).

    n=2,000,000 por defecto (en vez de los 10M de simular_partido() para
    un solo partido) para que simular 9 partidos de un jalón sea ágil en
    la interfaz — sigue siendo una muestra grande, el error estándar de
    Monte Carlo con 2M sims es despreciable para fines de recomendación
    de apuestas (ver nota en simular_partido()).

    sesgo_por_equipo: opcional, se pasa tal cual a cada llamada de
    simular_partido() (ver calcular_lambdas() para el detalle) —
    normalmente la salida de
    liga_mx_supabase.calcular_sesgo_por_equipo(historial_predicciones).

    NO guarda nada en Supabase — solo simula y arma el paquete de
    resultados. El guardado real (guardar_prediccion()/guardar_apuestas()
    de liga_mx_supabase.py) se hace aparte, en app.py o en
    liga_mx_supabase.guardar_jornada_completa(), para no acoplar este
    módulo (que no sabe nada de Supabase) con la capa de persistencia.

    Devuelve:
        {
          "jornada": int,
          "partidos": [
              {
                "local": str, "visitante": str, "arbitro": str,
                "resultado_sim": dict,      # salida de simular_partido()
                "apuestas": list,           # salida de analizar_apuestas()
                "parlay": dict | None,      # salida de armar_parlay()
              },
              ...
          ],
        }
    """
    if jornada is None:
        jornada = detectar_jornada_actual()
    if jornada is None:
        return {"jornada": None, "partidos": []}

    resultados = []
    for local, visit, jorn, estadio, resultado_real, arbitro in partidos_de_jornada(jornada):
        if resultado_real is not None:
            # ya se jugó de verdad — no tiene caso "simular" un resultado
            # que ya conocemos; se omite del paquete de simulación.
            continue
        r = simular_partido(local, visit, n=n, peso_elo=peso_elo,
                             peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
                             factor_clima=factor_clima, sesgo_por_equipo=sesgo_por_equipo)
        apuestas = analizar_apuestas(local, visit, r, mercados_suspendidos=mercados_suspendidos)
        parlay = armar_parlay(apuestas)
        resultados.append({
            "local": local, "visitante": visit,
            "arbitro": r.get("arbitro", "Sin asignar"),
            "resultado_sim": r,
            "apuestas": apuestas,
            "parlay": parlay,
        })

    return {"jornada": jornada, "partidos": resultados}


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
