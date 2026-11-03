"""
liga_mx_motor_poisson.py — Motor de goles ajustado por máxima verosimilitud.

QUÉ HACE
Estima, con los partidos reales, un modelo de Poisson tipo Dixon-Coles:

    log λ_local  = mu + localia + ataque[local]  + defensa[visitante]
    log λ_visita = mu +           ataque[visita] + defensa[local]

y la corrección rho de Dixon-Coles para 0-0 / 1-0 / 0-1 / 1-1. Todo sale
de los datos: la localía y rho ya no son números fijos a mano.

POR QUÉ (diagnóstico del 2/nov/2026, re-predicción a ciegas de los 134
partidos jugados del Apertura, cada jornada solo con jornadas previas):
el motor anterior (FUERZA_ATAQUE/DEFENSA del Clausura + EMA + split
local/visita + ×1.12 + bono de altitud) daba log-loss 1X2 de 1.233, peor
que 33/33/33 (1.099). Dos causas: la localía se contaba tres veces y las
diferencias entre equipos estaban infladas (goles por partido de un solo
torneo, sin regresión a la media). Este motor dio 1.078, estable en toda
la rejilla probada de parámetros (1.077–1.095).

CÓMO EVITA EL RUIDO
  - Shrinkage (penalización ridge, REGULARIZACION): ataque/defensa se
    jalan hacia 0 (= promedio de liga); un equipo necesita evidencia de
    varios partidos para separarse del resto.
  - Clausura 2026 como prior con PESO_CLAUSURA (0.6 por partido).
  - Decaimiento temporal: un partido del Apertura pesa
    exp(-DECAIMIENTO_POR_JORNADA × jornadas de antigüedad).

Solo numpy (sin scipy, que no está en requirements.txt). El ajuste toma
~0.1 s con ~300 partidos.
"""
import math
import numpy as np

from liga_mx_backtesting import CLAUSURA_2026_PARTIDOS

# ── Parámetros (no se afinaron contra el Apertura: se eligió el centro
# de una rejilla donde todos los valores daban resultados parecidos) ──
REGULARIZACION = 5.0
PESO_CLAUSURA = 0.6
DECAIMIENTO_POR_JORNADA = 0.05
ITERACIONES = 4000
TASA_APRENDIZAJE = 0.05
RHO_MIN, RHO_MAX, RHO_PASO = -0.20, 0.10, 0.01
RHO_DEFAULT = -0.13  # Dixon & Coles (1997); solo si no hay datos


def datos_entrenamiento(partidos: list, jornada_objetivo: int = None) -> list:
    """
    [(local, visita, gh, ga, peso), ...] con el Clausura 2026 completo
    (peso PESO_CLAUSURA) más los partidos del Apertura que ya tienen
    resultado en `partidos` (tuplas de PARTIDOS), con decaimiento según
    su distancia a `jornada_objetivo` (por defecto, la última jornada con
    resultados + 1).
    """
    jugados = [p for p in partidos if p[4] is not None]
    if jornada_objetivo is None:
        jornada_objetivo = max((p[2] for p in jugados), default=0) + 1
    filas = [(h, v, g[0], g[1], PESO_CLAUSURA) for h, v, _j, g in CLAUSURA_2026_PARTIDOS]
    for local, visit, jornada, _est, (gh, ga), _arb in jugados:
        antiguedad = max(jornada_objetivo - jornada, 0)
        filas.append((local, visit, gh, ga, math.exp(-DECAIMIENTO_POR_JORNADA * antiguedad)))
    return filas


def _log_tau(gh, ga, lh, la, rho):
    """log del factor tau de Dixon-Coles, vectorizado."""
    tau = np.ones_like(lh)
    m00 = (gh == 0) & (ga == 0)
    m10 = (gh == 1) & (ga == 0)
    m01 = (gh == 0) & (ga == 1)
    m11 = (gh == 1) & (ga == 1)
    tau[m00] = 1 - lh[m00] * la[m00] * rho
    tau[m10] = 1 + la[m10] * rho
    tau[m01] = 1 + lh[m01] * rho
    tau[m11] = 1 - rho
    return np.log(np.maximum(tau, 1e-9))


def ajustar_motor(filas: list, equipos: list) -> dict:
    """
    Ajusta mu, localía, ataque y defensa por máxima verosimilitud
    penalizada (Poisson ponderado), y luego rho por búsqueda en rejilla
    sobre la verosimilitud Dixon-Coles con esos lambdas.

    Devuelve {"mu", "localia", "rho", "ataque": {eq: float},
    "defensa": {eq: float}, "n_partidos": int} en escala logarítmica
    (0 = promedio de liga). Un equipo sin partidos queda en 0.
    """
    equipos = sorted(set(equipos) | {f[0] for f in filas} | {f[1] for f in filas})
    idx = {e: i for i, e in enumerate(equipos)}
    T = len(equipos)
    if not filas:
        return {"mu": math.log(1.37), "localia": 0.0, "rho": RHO_DEFAULT,
                "ataque": {e: 0.0 for e in equipos}, "defensa": {e: 0.0 for e in equipos}, "n_partidos": 0}

    H = np.array([idx[f[0]] for f in filas])
    A = np.array([idx[f[1]] for f in filas])
    gh = np.array([f[2] for f in filas], dtype=float)
    ga = np.array([f[3] for f in filas], dtype=float)
    w = np.array([f[4] for f in filas], dtype=float)
    W = w.sum()

    ataque = np.zeros(T)
    defensa = np.zeros(T)
    mu = math.log(max((w * (gh + ga)).sum() / (2 * W), 0.1))
    localia = 0.0
    paso_equipo = TASA_APRENDIZAJE * T / 2
    for _ in range(ITERACIONES):
        lh = np.exp(mu + localia + ataque[H] + defensa[A])
        la = np.exp(mu + ataque[A] + defensa[H])
        rh = w * (gh - lh)
        ra = w * (ga - la)
        g_at = np.bincount(H, rh, T) + np.bincount(A, ra, T) - 2 * REGULARIZACION * ataque
        g_de = np.bincount(A, rh, T) + np.bincount(H, ra, T) - 2 * REGULARIZACION * defensa
        mu += TASA_APRENDIZAJE * (rh.sum() + ra.sum()) / W
        localia += TASA_APRENDIZAJE * rh.sum() / W
        ataque += paso_equipo * g_at / W
        defensa += paso_equipo * g_de / W
        ataque -= ataque.mean()
        defensa -= defensa.mean()

    lh = np.exp(mu + localia + ataque[H] + defensa[A])
    la = np.exp(mu + ataque[A] + defensa[H])
    mejor_rho, mejor_ll = RHO_DEFAULT, -math.inf
    for rho in np.arange(RHO_MIN, RHO_MAX + 1e-9, RHO_PASO):
        ll = float((w * _log_tau(gh, ga, lh, la, rho)).sum())
        if ll > mejor_ll:
            mejor_rho, mejor_ll = float(round(rho, 2)), ll

    return {
        "mu": float(mu), "localia": float(localia), "rho": mejor_rho,
        "ataque": {e: float(ataque[idx[e]]) for e in equipos},
        "defensa": {e: float(defensa[idx[e]]) for e in equipos},
        "n_partidos": len(filas),
    }


def ajustar_desde_partidos(partidos: list, equipos: list, jornada_objetivo: int = None) -> dict:
    """Atajo: datos_entrenamiento() + ajustar_motor()."""
    return ajustar_motor(datos_entrenamiento(partidos, jornada_objetivo), equipos)


def lambdas_motor(params: dict, local: str, visita: str, peso_fuerza: float = 1.0) -> tuple:
    """
    (λ_local, λ_visita) según el motor ajustado. peso_fuerza escala las
    diferencias entre equipos (1.0 = lo estimado, 0.0 = todos iguales);
    es lo que recibe el slider peso_elo de calcular_lambdas().
    """
    at, de = params["ataque"], params["defensa"]
    lh = math.exp(params["mu"] + params["localia"] + peso_fuerza * (at.get(local, 0.0) + de.get(visita, 0.0)))
    la = math.exp(params["mu"] + peso_fuerza * (at.get(visita, 0.0) + de.get(local, 0.0)))
    return lh, la


def resumen_motor(params: dict) -> list:
    """
    Tabla legible por equipo: goles esperados a favor y en contra contra
    un rival promedio en cancha neutral, ordenada por diferencia.
    """
    base = math.exp(params["mu"])
    filas = []
    for eq in params["ataque"]:
        gf = base * math.exp(params["ataque"][eq])
        gc = base * math.exp(params["defensa"][eq])
        filas.append({"equipo": eq, "gf_esperados": round(gf, 2), "gc_esperados": round(gc, 2),
                      "diferencia": round(gf - gc, 2)})
    filas.sort(key=lambda f: f["diferencia"], reverse=True)
    return filas
