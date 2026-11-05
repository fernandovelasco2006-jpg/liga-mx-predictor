"""
liga_mx_walkforward.py — Backtest a ciegas del motor de goles sobre el
Apertura en curso.

Para cada jornada con resultados, vuelve a predecir sus partidos usando
SOLO los resultados de las jornadas anteriores (como si fuera el día del
partido): se recalculan Elo, EMA, forma real y el motor ajustado con
PARTIDOS recortado. Las probabilidades se calculan exactas (Poisson +
Dixon-Coles sumando marcadores), sin Monte Carlo, así que corre en
segundos.

A diferencia de liga_mx_backtesting.py (Clausura 2026, que el modelo ya
"vio" al construir sus priors), aquí ninguna predicción conoce el
partido que predice, así que sirve para comparar motores. No incluye
clima ni sesgo por equipo (vienen de APIs y de Supabase).

Uso:  python3 liga_mx_walkforward.py            (reporte)
      python3 liga_mx_walkforward.py --evidencia (filas de evidencia en JSON)
"""
import json
import math
import sys

import liga_mx_algoritmo as alg
import liga_mx_elo_update as elo_update
from liga_mx_motor_poisson import ajustar_desde_partidos

MAX_GOLES = 10
UMBRAL_APUESTA = 80.0


def _probabilidades(lam_h: float, lam_a: float, rho: float) -> dict:
    """1X2, Over 2.5, Ambos Marcan y las líneas de goles que recomienda
    analizar_apuestas(), con Dixon-Coles, en %."""
    ph = [math.exp(-lam_h) * lam_h ** k / math.factorial(k) for k in range(MAX_GOLES + 1)]
    pa = [math.exp(-lam_a) * lam_a ** k / math.factorial(k) for k in range(MAX_GOLES + 1)]
    m = {}
    for x in range(MAX_GOLES + 1):
        for y in range(MAX_GOLES + 1):
            tau = alg._tau_dixon_coles(x, y, lam_h, lam_a, rho=rho)
            m[(x, y)] = ph[x] * pa[y] * max(tau, 1e-6)
    total = sum(m.values())

    def suma(cond):
        return sum(v for (x, y), v in m.items() if cond(x, y)) / total * 100

    p1, px = suma(lambda x, y: x > y), suma(lambda x, y: x == y)
    return {"1": p1, "X": px, "2": 100 - p1 - px,
            "over15": suma(lambda x, y: x + y >= 2), "over25": suma(lambda x, y: x + y >= 3),
            "over35": suma(lambda x, y: x + y >= 4),
            "btts": suma(lambda x, y: x >= 1 and y >= 1)}


def _estado_a_jornada(partidos_recortados: list, jornada: int):
    alg.PARTIDOS = partidos_recortados
    alg.ELO_ACTUALIZADO = elo_update.actualizar_elo(partidos_recortados, alg.ELO_BASE)
    fa, fd = elo_update.actualizar_fuerza_ataque_defensa(partidos_recortados, alg.FUERZA_ATAQUE_BASE,
                                                         alg.FUERZA_DEFENSA_BASE)
    alg.FUERZA_ATAQUE, alg.FUERZA_DEFENSA = fa, fd
    alg._elo_promedio_actualizado = sum(alg.ELO_ACTUALIZADO.values()) / len(alg.ELO_ACTUALIZADO)
    alg.PARAMS_MOTOR = ajustar_desde_partidos(partidos_recortados, alg.EQUIPOS, jornada_objetivo=jornada)


def _ll_binaria(p_pct: float, ocurrio: bool) -> float:
    p = min(max(p_pct / 100, 1e-6), 1 - 1e-6)
    return -math.log(p if ocurrio else 1 - p)


def backtest(motor: str = None) -> dict:
    """
    Re-predice a ciegas todos los partidos jugados con el motor indicado
    ("poisson_mle" o "heredado"; None = alg.MOTOR_GOLES). Restaura el
    estado del módulo al terminar.
    """
    motor = motor or alg.MOTOR_GOLES
    originales = {k: getattr(alg, k) for k in ("PARTIDOS", "ELO_ACTUALIZADO", "FUERZA_ATAQUE", "FUERZA_DEFENSA",
                                               "_elo_promedio_actualizado", "PARAMS_MOTOR")}
    completos = list(originales["PARTIDOS"])
    jugados = [p for p in completos if p[4] is not None]
    rho = None
    filas = []
    try:
        for jornada in sorted({p[2] for p in jugados}):
            recortados = [p if (p[4] is not None and p[2] < jornada) else (*p[:4], None, p[5]) for p in completos]
            _estado_a_jornada(recortados, jornada)
            rho = alg.PARAMS_MOTOR["rho"] if motor == "poisson_mle" else alg.RHO_DIXON_COLES_HEREDADO
            for local, visit, _j, _e, (gh, ga), _a in [p for p in jugados if p[2] == jornada]:
                lam_h, lam_a = alg.calcular_lambdas(local, visit, motor=motor)
                pr = _probabilidades(lam_h, lam_a, rho)
                filas.append({"local": local, "visitante": visit, "jornada": jornada,
                              "gh": gh, "ga": ga, "lam_h": lam_h, "lam_a": lam_a, **pr})
    finally:
        for k, v in originales.items():
            setattr(alg, k, v)

    return {"motor": motor, "filas": filas, **_metricas(filas)}


def _metricas(filas: list) -> dict:
    n = len(filas)
    if not n:
        return {"n": 0}
    ll = br = ll_o25 = ll_btts = 0.0
    apuestas = {"n": 0, "aciertos": 0, "prometido": 0.0}
    for f in filas:
        gh, ga = f["gh"], f["ga"]
        y = {"1": gh > ga, "X": gh == ga, "2": gh < ga}
        ocurrio = "1" if y["1"] else ("X" if y["X"] else "2")
        ll += -math.log(max(f[ocurrio] / 100, 1e-6))
        br += sum((f[k] / 100 - (1.0 if y[k] else 0.0)) ** 2 for k in y)
        ll_o25 += _ll_binaria(f["over25"], gh + ga >= 3)
        ll_btts += _ll_binaria(f["btts"], gh > 0 and ga > 0)
        # Selecciones de goles que pasarían el umbral de 80% (sin
        # calibración): 1X2, doble oportunidad, Over 1.5, Under 2.5 y BTTS.
        candidatas = [(f["1"], y["1"]), (f["2"], y["2"]), (f["1"] + f["X"], not y["2"]),
                      (f["2"] + f["X"], not y["1"]), (f["over15"], gh + ga >= 2),
                      (100 - f["over25"], gh + ga <= 2), (f["btts"], gh > 0 and ga > 0),
                      (100 - f["btts"], not (gh > 0 and ga > 0))]
        for p, ok in candidatas:
            if p >= UMBRAL_APUESTA:
                apuestas["n"] += 1
                apuestas["aciertos"] += ok
                apuestas["prometido"] += p
    prom = lambda k: sum(f[k] for f in filas) / n
    return {
        "n": n,
        "log_loss_1x2": round(ll / n, 4),
        "brier_1x2": round(br / n, 4),
        "log_loss_over25": round(ll_o25 / n, 4),
        "log_loss_btts": round(ll_btts / n, 4),
        "prob_media": {"1": round(prom("1"), 1), "X": round(prom("X"), 1), "2": round(prom("2"), 1)},
        "real": {"1": round(sum(f["gh"] > f["ga"] for f in filas) / n * 100, 1),
                 "X": round(sum(f["gh"] == f["ga"] for f in filas) / n * 100, 1),
                 "2": round(sum(f["gh"] < f["ga"] for f in filas) / n * 100, 1)},
        "goles_esperados": (round(prom("lam_h"), 2), round(prom("lam_a"), 2)),
        "goles_reales": (round(sum(f["gh"] for f in filas) / n, 2), round(sum(f["ga"] for f in filas) / n, 2)),
        "apuestas_80": {"n": apuestas["n"],
                        "prometido": round(apuestas["prometido"] / apuestas["n"], 1) if apuestas["n"] else None,
                        "real": round(apuestas["aciertos"] / apuestas["n"] * 100, 1) if apuestas["n"] else None},
    }


def reporte_markdown() -> str:
    """Tabla comparativa motor actual vs. heredado vs. 33/33/33."""
    actual = backtest("poisson_mle")
    heredado = backtest("heredado")
    if not actual.get("n"):
        return "Sin partidos jugados todavía para el backtest."
    uniforme = round(math.log(3), 4)
    lineas = [
        f"**Backtest a ciegas del motor de goles** ({actual['n']} partidos del Apertura, cada jornada "
        f"predicha solo con las anteriores). Menor es mejor.",
        "",
        "| Motor | Log-loss 1X2 | Brier 1X2 | Log-loss Over 2.5 | Log-loss Ambos Marcan | "
        "Apuestas ≥80%: prometido → real |",
        "|---|---|---|---|---|---|",
    ]
    for nombre, r in (("Poisson ajustado (actual)", actual), ("Heredado", heredado)):
        a = r["apuestas_80"]
        ap = f"{a['prometido']}% → {a['real']}% ({a['n']})" if a["n"] else "—"
        lineas.append(f"| {nombre} | {r['log_loss_1x2']} | {r['brier_1x2']} | {r['log_loss_over25']} | "
                      f"{r['log_loss_btts']} | {ap} |")
    lineas.append(f"| 33/33/33 | {uniforme} | 0.6667 | — | — | — |")
    lineas += ["", f"Goles esperados local/visita (actual): {actual['goles_esperados']} · reales: "
                   f"{actual['goles_reales']}"]
    return "\n".join(lineas)


# Piso de confianza para la evidencia: la isotónica necesita ver también
# los tramos de 50-80% para saber cuánto bajar los de 80%+.
PISO_EVIDENCIA = 50.0


def _candidatas(f: dict) -> list:
    """(mercado, confianza cruda, acierto) de cada selección que
    analizar_apuestas() puede recomendar y que sale solo del motor de
    goles. acierto None = nula (empate en DNB), no cuenta."""
    gh, ga = f["gh"], f["ga"]
    p1, px, p2 = f["1"], f["X"], f["2"]
    goles = gh + ga
    empate = gh == ga
    out = [
        ("Resultado (1X2)", p1, gh > ga), ("Resultado (1X2)", p2, gh < ga),
        ("Doble Oportunidad", min(p1 + px, 99), gh >= ga), ("Doble Oportunidad", min(p2 + px, 99), gh <= ga),
        ("Total Goles", f["over15"], goles >= 2), ("Total Goles", f["over25"], goles >= 3),
        ("Total Goles", f["over35"], goles >= 4), ("Total Goles", 100 - f["over15"], goles <= 1),
        ("Total Goles", 100 - f["over25"], goles <= 2),
        ("Ambos Marcan", f["btts"], gh > 0 and ga > 0), ("Ambos Marcan", 100 - f["btts"], not (gh > 0 and ga > 0)),
    ]
    if p1 + p2 > 0:
        out += [("Empate Sin Apuesta", p1 / (p1 + p2) * 100, None if empate else gh > ga),
                ("Empate Sin Apuesta", p2 / (p1 + p2) * 100, None if empate else gh < ga)]
    return out


def evidencia_backtest(resultado: dict = None) -> list:
    """
    Apuestas "a ciegas" del motor actual, con el mismo formato que las
    filas de apuestas_historial_ligamx (mercado, jornada, confianza,
    confianza_cruda, acierto, version_modelo). Sirven de evidencia de
    arranque para calcular_mercados_suspendidos() y
    calibrar_confianza_por_mercado() mientras el motor actual todavía no
    junta apuestas reales evaluadas: sin esto, los mercados de goles se
    juzgaban con apuestas del motor anterior.
    """
    r = resultado or backtest(alg.MOTOR_GOLES)
    filas = []
    for f in r.get("filas", []):
        for mercado, p, ok in _candidatas(f):
            if ok is None or p < PISO_EVIDENCIA:
                continue
            p = round(p, 1)
            filas.append({"mercado": mercado, "jornada": f["jornada"], "local": f["local"],
                          "visitante": f["visitante"], "confianza": p, "confianza_cruda": p,
                          "acierto": bool(ok), "version_modelo": alg.VERSION_MODELO, "origen": "backtest"})
    return filas


if __name__ == "__main__":
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia_backtest()))
    else:
        print(reporte_markdown())
