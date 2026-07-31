# ─────────────────────────────────────────────────────────────────────────
# liga_mx_elo_update.py — Recalibración dinámica del modelo, jornada a
# jornada, para Liga MX.
#
# QUÉ HACE
# Después de cada jornada jugada, ajusta dos cosas a partir de los
# resultados reales que ya tienes cargados en PARTIDOS (skeleton):
#
#   1. ELO de cada equipo — fórmula Elo estándar de fútbol de clubes
#      (mismo criterio que usa clubelo.com / World Football Elo Ratings):
#      ventaja de local + multiplicador por diferencia de goles.
#   2. FUERZA_ATAQUE / FUERZA_DEFENSA — media móvil exponencial (EMA) que
#      mueve el valor de cada equipo hacia lo que REALMENTE anotó/recibió
#      en cada partido jugado.
#
# CÓMO SE INTEGRA (sin tocar el skeleton ni pedirte una base de datos)
# Como PARTIDOS ya acumula los resultados reales conforme me los vas
# pasando jornada a jornada, este módulo simplemente "reproduce" desde
# cero el historial completo cada vez que arranca la app: parte de los
# valores base (ELO / FUERZA_ATAQUE / FUERZA_DEFENSA del Clausura 2026,
# tal cual están en liga_mx_predictor_skeleton.py y liga_mx_algoritmo.py)
# y les aplica, en orden de jornada, el ajuste de cada partido jugado.
#
# Los diccionarios BASE nunca se modifican — siguen siendo el "prior" de
# arranque de temporada. liga_mx_algoritmo.py importa las funciones de
# aquí y calcula las versiones ACTUALIZADAS (ELO_ACTUALIZADO,
# FUERZA_ATAQUE_ACTUALIZADA, FUERZA_DEFENSA_ACTUALIZADA), que son las que
# de verdad usa calcular_lambdas() para las predicciones.
#
# No hay que llamar nada a mano: basta con que sigas actualizando
# PARTIDOS con los resultados reales (como ya hacemos cada jornada) y el
# modelo se recalibra solo la próxima vez que corra la app.
# ─────────────────────────────────────────────────────────────────────────

# ── Parámetros ajustables ───────────────────────────────────────────────
K_FACTOR = 20            # sensibilidad del ajuste Elo por partido.
                          # Referencia: selecciones nacionales usan 30-60;
                          # ligas domésticas de clubes suelen usar 15-25.
VENTAJA_LOCAL_ELO = 65    # puntos Elo que se le suman al local antes de
                          # calcular el resultado esperado (clubelo.com
                          # usa un valor similar para ligas de clubes).
ALPHA_FUERZA = 0.15       # peso del partido más reciente en la media móvil
                          # de FUERZA_ATAQUE/FUERZA_DEFENSA (0.15 = cada
                          # partido mueve ~15% el valor hacia lo observado,
                          # dejando 85% del historial/calibración previa).


def _multiplicador_goleada(diferencia_goles: int) -> float:
    """
    Multiplicador según el margen de la victoria (criterio World Football
    Elo Ratings): un resultado ajustado (0 o 1 gol de diferencia) no pesa
    más que un empate cerrado; goleadas sí mueven más el rating.
    """
    dif = abs(diferencia_goles)
    if dif <= 1:
        return 1.0
    if dif == 2:
        return 1.5
    return (11 + dif) / 8


def _partidos_jugados_en_orden(partidos: list) -> list:
    """Filtra solo los partidos con resultado real y los ordena por
    jornada (preservando el orden original dentro de cada jornada — no
    afecta el cálculo, ya que en un torneo de todos-contra-todos ningún
    equipo juega dos veces en la misma jornada)."""
    jugados = [p for p in partidos if p[4] is not None]
    return sorted(jugados, key=lambda p: p[2])


def actualizar_elo(partidos: list, elo_base: dict) -> dict:
    """
    Reproduce, en orden de jornada, cada partido jugado y devuelve un
    diccionario NUEVO con el Elo actualizado de los 18 equipos. No
    modifica elo_base.
    """
    elo = dict(elo_base)
    promedio_base = sum(elo_base.values()) / len(elo_base)

    for local, visit, jornada, estadio, resultado, arbitro in _partidos_jugados_en_orden(partidos):
        gh, ga = resultado
        elo_local = elo.get(local, promedio_base)
        elo_visit = elo.get(visit, promedio_base)

        dr = (elo_local + VENTAJA_LOCAL_ELO) - elo_visit
        esperado_local = 1 / (10 ** (-dr / 400) + 1)

        if gh > ga:
            resultado_local = 1.0
        elif gh == ga:
            resultado_local = 0.5
        else:
            resultado_local = 0.0

        mult = _multiplicador_goleada(gh - ga)
        delta = K_FACTOR * mult * (resultado_local - esperado_local)

        elo[local] = elo_local + delta
        elo[visit] = elo_visit - delta

    return elo


def actualizar_fuerza_ataque_defensa(partidos: list, fuerza_ataque_base: dict,
                                      fuerza_defensa_base: dict) -> tuple:
    """
    Ajusta FUERZA_ATAQUE y FUERZA_DEFENSA con una media móvil exponencial:
    cada partido jugado mueve el valor de cada equipo un ALPHA_FUERZA hacia
    los goles que realmente anotó/recibió ese partido. Devuelve
    (nueva_fuerza_ataque, nueva_fuerza_defensa) — no modifica los
    diccionarios base.
    """
    ataque = dict(fuerza_ataque_base)
    defensa = dict(fuerza_defensa_base)
    prom_ataque = sum(fuerza_ataque_base.values()) / len(fuerza_ataque_base)
    prom_defensa = sum(fuerza_defensa_base.values()) / len(fuerza_defensa_base)

    for local, visit, jornada, estadio, resultado, arbitro in _partidos_jugados_en_orden(partidos):
        gh, ga = resultado

        a_local = ataque.get(local, prom_ataque)
        d_local = defensa.get(local, prom_defensa)
        a_visit = ataque.get(visit, prom_ataque)
        d_visit = defensa.get(visit, prom_defensa)

        ataque[local] = (1 - ALPHA_FUERZA) * a_local + ALPHA_FUERZA * gh
        defensa[local] = (1 - ALPHA_FUERZA) * d_local + ALPHA_FUERZA * ga
        ataque[visit] = (1 - ALPHA_FUERZA) * a_visit + ALPHA_FUERZA * ga
        defensa[visit] = (1 - ALPHA_FUERZA) * d_visit + ALPHA_FUERZA * gh

    return ataque, defensa


def resumen_movimiento_elo(elo_base: dict, elo_actualizado: dict, top: int = None) -> list:
    """
    Lista de (equipo, elo_antes, elo_despues, delta), ordenada de mayor a
    menor movimiento absoluto — útil para mostrar en la interfaz qué
    equipos subieron/bajaron más tras la última jornada procesada.
    Si `top` se especifica, devuelve solo los primeros N.
    """
    filas = []
    for equipo in elo_base:
        antes = elo_base[equipo]
        despues = elo_actualizado.get(equipo, antes)
        filas.append((equipo, round(antes, 1), round(despues, 1), round(despues - antes, 1)))
    filas.sort(key=lambda f: abs(f[3]), reverse=True)
    return filas[:top] if top else filas


def n_partidos_procesados(partidos: list) -> int:
    """Cuántos partidos jugados se usaron para la recalibración actual —
    útil para mostrar '(basado en N partidos)' en la interfaz."""
    return len(_partidos_jugados_en_orden(partidos))
