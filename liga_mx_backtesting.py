"""
liga_mx_backtesting.py — Backtesting formal del modelo contra el Clausura
2026 COMPLETO (153 partidos, 17 jornadas, fase regular — sin Liguilla).

A diferencia del historial de predicciones del Apertura 2026 (que solo
tiene los pocos partidos que se han jugado hasta ahora), este módulo
permite correr el modelo ACTUAL (con toda la calibración de hoy: Elo,
forma real, árbitro dinámico, sesgo por equipo si aplica, etc.) contra
un torneo COMPLETO ya conocido, dando una muestra de 153 partidos en vez
de un puñado — la prueba más sólida disponible de qué tan bien calibrado
está el modelo.

Fuente de los resultados: recopilados y verificados por el usuario
(cuadran exactamente: 153 partidos, 18 equipos con 17 PJ cada uno, 17
jornadas de 9 partidos sin repetir equipo). "Mazatlán" se mapea a
"Atlante" (mismo criterio que el resto del proyecto usa para todos los
datos heredados del Clausura 2026, ya que Atlante ocupó su lugar en el
Apertura 2026 tras el ascenso).

IMPORTANTE — limitación metodológica honesta, y REGLA DE USO explícita:
el modelo actual usa FUERZA_ATAQUE/FUERZA_DEFENSA/TARJETAS_EQUIPO_LIGAMX
que YA fueron calibradas a partir de este mismo Clausura 2026 (ver
liga_mx_algoritmo.py) — así que este backtesting NO es una prueba "a
ciegas" en el sentido estricto. El modelo ya "vio" estos datos agregados
al construir sus priors, así que cualquier número de mejora que arroje
está inflado por diseño (el modelo está parcialmente "recordando" datos
que ya conocía, no prediciendo información nueva).

REGLA: este módulo sirve ÚNICAMENTE como sanity check (¿el código corre
sin errores? ¿las probabilidades tienen sentido? ¿el modelo le gana al
menos a un baseline tonto, aunque sea por poco?) — NUNCA como señal para
ajustar peso_elo, peso_altitud, peso_arbitro, peso_forma_elo, o
cualquier otro parámetro del modelo. Ajustar esos pesos para "mejorar el
resultado del Clausura" sería overfitting/data leakage: optimizar contra
el examen que ya tienes las respuestas, sin mejorar la capacidad real
de predecir partidos futuros.

La ÚNICA fuente confiable para decidir si ajustar el modelo es el
historial REAL del Apertura 2026 en Supabase (predicciones_ligamx +
apuestas_historial_ligamx) — cada predicción ahí se guardó ANTES de
conocer el resultado, así que es genuinamente "a ciegas". Usa
liga_mx_supabase.calcular_brier_score(), calcular_calibracion_por_bin()
y comparar_modelo_vs_baseline() sobre ESE historial para cualquier
decisión de calibración real.
"""

CLAUSURA_2026_PARTIDOS = [
    ("Atlante", "FC Juarez", 1, (1, 2)),
    ("Atlas", "Puebla", 1, (1, 0)),
    ("Tijuana", "America", 1, (0, 0)),
    ("Guadalajara", "Pachuca", 1, (2, 0)),
    ("Leon", "Cruz Azul", 1, (2, 1)),
    ("Santos Laguna", "Necaxa", 1, (1, 3)),
    ("Monterrey", "Toluca", 1, (0, 1)),
    ("Pumas UNAM", "Queretaro", 1, (1, 1)),
    ("Atletico San Luis", "Tigres", 1, (1, 2)),
    ("Puebla", "Atlante", 2, (2, 1)),
    ("Necaxa", "Monterrey", 2, (0, 2)),
    ("Pachuca", "Leon", 2, (2, 1)),
    ("FC Juarez", "Guadalajara", 2, (0, 1)),
    ("Cruz Azul", "Atlas", 2, (2, 0)),
    ("Queretaro", "Tijuana", 2, (1, 2)),
    ("America", "Atletico San Luis", 2, (0, 2)),
    ("Tigres", "Pumas UNAM", 2, (0, 1)),
    ("Toluca", "Santos Laguna", 2, (3, 1)),
    ("Atlante", "Monterrey", 3, (1, 5)),
    ("Necaxa", "Atlas", 3, (0, 1)),
    ("Guadalajara", "Queretaro", 3, (2, 1)),
    ("Tigres", "Toluca", 3, (0, 0)),
    ("Tijuana", "Atletico San Luis", 3, (1, 1)),
    ("Cruz Azul", "Puebla", 3, (1, 0)),
    ("Pumas UNAM", "Leon", 3, (1, 1)),
    ("Santos Laguna", "FC Juarez", 3, (2, 2)),
    ("Pachuca", "America", 3, (0, 0)),
    ("Puebla", "Toluca", 4, (0, 0)),
    ("Pumas UNAM", "Santos Laguna", 4, (4, 0)),
    ("FC Juarez", "Cruz Azul", 4, (3, 4)),
    ("America", "Necaxa", 4, (2, 0)),
    ("Atlas", "Atlante", 4, (1, 0)),
    ("Atletico San Luis", "Guadalajara", 4, (2, 3)),
    ("Monterrey", "Tijuana", 4, (2, 2)),
    ("Leon", "Tigres", 4, (1, 2)),
    ("Queretaro", "Pachuca", 4, (0, 0)),
    ("Necaxa", "Atletico San Luis", 5, (4, 1)),
    ("Tigres", "Santos Laguna", 5, (5, 1)),
    ("Tijuana", "Puebla", 5, (0, 0)),
    ("Atlante", "Guadalajara", 5, (1, 2)),
    ("Toluca", "Cruz Azul", 5, (1, 1)),
    ("Queretaro", "Leon", 5, (2, 0)),
    ("Atlas", "Pumas UNAM", 5, (2, 2)),
    ("Pachuca", "FC Juarez", 5, (2, 0)),
    ("America", "Monterrey", 5, (1, 0)),
    ("Puebla", "Pumas UNAM", 6, (2, 3)),
    ("Toluca", "Tijuana", 6, (1, 0)),
    ("Atletico San Luis", "Queretaro", 6, (3, 0)),
    ("Pachuca", "Atlas", 6, (3, 1)),
    ("Monterrey", "Leon", 6, (1, 0)),
    ("FC Juarez", "Necaxa", 6, (1, 2)),
    ("Guadalajara", "America", 6, (1, 0)),
    ("Cruz Azul", "Tigres", 6, (2, 1)),
    ("Santos Laguna", "Atlante", 6, (1, 2)),
    ("Tigres", "Pachuca", 7, (1, 2)),
    ("Puebla", "America", 7, (0, 4)),
    ("Atlas", "Atletico San Luis", 7, (3, 2)),
    ("Leon", "Santos Laguna", 7, (2, 1)),
    ("Necaxa", "Toluca", 7, (0, 3)),
    ("Cruz Azul", "Guadalajara", 7, (2, 1)),
    ("Tijuana", "Atlante", 7, (1, 1)),
    ("Pumas UNAM", "Monterrey", 7, (2, 0)),
    ("Queretaro", "FC Juarez", 7, (1, 1)),
    ("Atlante", "Pachuca", 8, (1, 0)),
    ("Queretaro", "Santos Laguna", 8, (2, 2)),
    ("FC Juarez", "Atlas", 8, (3, 1)),
    ("Tijuana", "Pumas UNAM", 8, (1, 1)),
    ("Atletico San Luis", "Puebla", 8, (0, 1)),
    ("Toluca", "Guadalajara", 8, (2, 0)),
    ("Monterrey", "Cruz Azul", 8, (0, 2)),
    ("Leon", "Necaxa", 8, (2, 1)),
    ("America", "Tigres", 8, (1, 4)),
    ("Pachuca", "Necaxa", 9, (2, 1)),
    ("Santos Laguna", "Cruz Azul", 9, (1, 2)),
    ("Atletico San Luis", "Atlante", 9, (4, 1)),
    ("Pumas UNAM", "Toluca", 9, (2, 3)),
    ("Monterrey", "Queretaro", 9, (4, 0)),
    ("Puebla", "Tigres", 9, (3, 1)),
    ("Atlas", "Tijuana", 9, (2, 1)),
    ("America", "FC Juarez", 9, (1, 2)),
    ("Guadalajara", "Leon", 9, (5, 0)),
    ("Atlante", "Leon", 10, (4, 2)),
    ("Necaxa", "Pumas UNAM", 10, (0, 1)),
    ("Cruz Azul", "Atletico San Luis", 10, (3, 0)),
    ("Queretaro", "America", 10, (1, 2)),
    ("Atlas", "Guadalajara", 10, (1, 2)),
    ("Pachuca", "Puebla", 10, (2, 1)),
    ("Tigres", "Monterrey", 10, (1, 0)),
    ("Toluca", "FC Juarez", 10, (3, 1)),
    ("Tijuana", "Santos Laguna", 10, (1, 2)),
    ("Puebla", "Necaxa", 11, (0, 0)),
    ("FC Juarez", "Monterrey", 11, (2, 2)),
    ("Atletico San Luis", "Pachuca", 11, (1, 1)),
    ("Guadalajara", "Santos Laguna", 11, (3, 0)),
    ("Toluca", "Atlas", 11, (1, 1)),
    ("Leon", "Tijuana", 11, (0, 3)),
    ("Pumas UNAM", "Cruz Azul", 11, (2, 2)),
    ("Tigres", "Queretaro", 11, (0, 0)),
    ("America", "Atlante", 11, (2, 0)),
    ("Necaxa", "Tijuana", 12, (3, 0)),
    ("Atlante", "Cruz Azul", 12, (1, 1)),
    ("Atlas", "Queretaro", 12, (0, 0)),
    ("Atletico San Luis", "Leon", 12, (1, 2)),
    ("Monterrey", "Guadalajara", 12, (2, 3)),
    ("Pumas UNAM", "America", 12, (1, 0)),
    ("Pachuca", "Toluca", 12, (1, 1)),
    ("Santos Laguna", "Puebla", 12, (2, 1)),
    ("FC Juarez", "Tigres", 12, (2, 1)),
    ("Puebla", "FC Juarez", 13, (1, 1)),
    ("Necaxa", "Atlante", 13, (2, 1)),
    ("Tijuana", "Tigres", 13, (1, 0)),
    ("Monterrey", "Atletico San Luis", 13, (1, 2)),
    ("Queretaro", "Toluca", 13, (1, 0)),
    ("Leon", "Atlas", 13, (2, 0)),
    ("Cruz Azul", "Pachuca", 13, (1, 2)),
    ("Santos Laguna", "America", 13, (1, 1)),
    ("Guadalajara", "Pumas UNAM", 13, (2, 2)),
    ("Puebla", "Leon", 14, (0, 1)),
    ("FC Juarez", "Tijuana", 14, (1, 2)),
    ("Queretaro", "Necaxa", 14, (3, 1)),
    ("Tigres", "Guadalajara", 14, (4, 1)),
    ("Atlas", "Monterrey", 14, (0, 0)),
    ("Pachuca", "Santos Laguna", 14, (4, 2)),
    ("America", "Cruz Azul", 14, (1, 1)),
    ("Pumas UNAM", "Atlante", 14, (3, 1)),
    ("Toluca", "Atletico San Luis", 14, (1, 1)),
    ("Atletico San Luis", "Pumas UNAM", 15, (0, 2)),
    ("Atlante", "Queretaro", 15, (1, 1)),
    ("Necaxa", "Tigres", 15, (1, 1)),
    ("Cruz Azul", "Tijuana", 15, (1, 1)),
    ("Monterrey", "Pachuca", 15, (1, 3)),
    ("Guadalajara", "Puebla", 15, (5, 0)),
    ("Leon", "FC Juarez", 15, (3, 1)),
    ("America", "Toluca", 15, (2, 1)),
    ("Santos Laguna", "Atlas", 15, (0, 1)),
    ("Pumas UNAM", "FC Juarez", 16, (4, 2)),
    ("Queretaro", "Cruz Azul", 16, (1, 1)),
    ("Monterrey", "Puebla", 16, (2, 1)),
    ("Leon", "America", 16, (2, 3)),
    ("Atlas", "Tigres", 16, (0, 0)),
    ("Atletico San Luis", "Santos Laguna", 16, (2, 0)),
    ("Atlante", "Toluca", 16, (4, 3)),
    ("Tijuana", "Pachuca", 16, (3, 1)),
    ("Necaxa", "Guadalajara", 16, (0, 0)),
    ("Puebla", "Queretaro", 17, (1, 2)),
    ("Pachuca", "Pumas UNAM", 17, (0, 2)),
    ("Tigres", "Atlante", 17, (5, 1)),
    ("Toluca", "Leon", 17, (4, 1)),
    ("Guadalajara", "Tijuana", 17, (0, 0)),
    ("FC Juarez", "Atletico San Luis", 17, (2, 1)),
    ("America", "Atlas", 17, (0, 1)),
    ("Santos Laguna", "Monterrey", 17, (3, 0)),
    ("Cruz Azul", "Necaxa", 17, (4, 1)),
]

# Verificación de integridad — se corre una vez al importar el módulo,
# no en cada llamada, para no pagar el costo cada vez.
assert len(CLAUSURA_2026_PARTIDOS) == 153, f"Se esperaban 153 partidos, hay {len(CLAUSURA_2026_PARTIDOS)}"


def correr_backtesting_clausura(n_sims: int = 200_000) -> dict:
    """
    Corre el modelo ACTUAL (calcular_lambdas() con su calibración de
    hoy) contra los 153 partidos reales del Clausura 2026, calcula el
    Brier Score real resultante, y lo compara contra el baseline simple
    — mismo criterio que liga_mx_supabase.comparar_modelo_vs_baseline(),
    pero sobre una muestra 30 veces más grande que el historial actual
    del Apertura 2026.

    n_sims=200,000 (no 10M) por partido — con 153 partidos, correr el
    valor por defecto de simular_partido() tardaría demasiado; 200k es
    suficiente para que el error estándar de Monte Carlo sea
    despreciable frente a las diferencias que importan aquí.

    Ver la limitación metodológica documentada al inicio del módulo:
    esto mide calibración/consistencia interna, no capacidad de
    generalización a datos nunca vistos por el modelo.

    Devuelve:
        {
          "n_partidos": 153,
          "brier_modelo": float,
          "brier_baseline": float,
          "mejora_pct": float,
          "accuracy_ganador": float,   # % de veces que el favorito del modelo ganó
          "por_jornada": [{"jornada": int, "brier_promedio": float}, ...],
        }
    """
    # Imports diferidos para evitar dependencia circular al cargar el
    # módulo (liga_mx_algoritmo importa cosas del skeleton, no de aquí).
    from liga_mx_algoritmo import simular_partido, simular_partido_baseline

    suma_brier_modelo = 0.0
    suma_brier_baseline = 0.0
    aciertos_ganador = 0
    brier_por_jornada = {}

    for local, visit, jornada, resultado in CLAUSURA_2026_PARTIDOS:
        gh, ga = resultado
        y_local = 1.0 if gh > ga else 0.0
        y_empate = 1.0 if gh == ga else 0.0
        y_visita = 1.0 if gh < ga else 0.0

        r = simular_partido(local, visit, n=n_sims)
        p_local, p_empate, p_visita = r["prob_home"] / 100, r["prob_draw"] / 100, r["prob_away"] / 100
        brier_modelo = (p_local - y_local) ** 2 + (p_empate - y_empate) ** 2 + (p_visita - y_visita) ** 2
        suma_brier_modelo += brier_modelo

        base = simular_partido_baseline(local, visit)
        pb_local, pb_empate, pb_visita = base["prob_home"] / 100, base["prob_draw"] / 100, base["prob_away"] / 100
        brier_baseline = (pb_local - y_local) ** 2 + (pb_empate - y_empate) ** 2 + (pb_visita - y_visita) ** 2
        suma_brier_baseline += brier_baseline

        favorito_prob = max(p_local, p_empate, p_visita)
        favorito_gano = (
            (favorito_prob == p_local and y_local == 1.0) or
            (favorito_prob == p_empate and y_empate == 1.0) or
            (favorito_prob == p_visita and y_visita == 1.0)
        )
        if favorito_gano:
            aciertos_ganador += 1

        if jornada not in brier_por_jornada:
            brier_por_jornada[jornada] = [0.0, 0]
        brier_por_jornada[jornada][0] += brier_modelo
        brier_por_jornada[jornada][1] += 1

    n = len(CLAUSURA_2026_PARTIDOS)
    brier_modelo_prom = suma_brier_modelo / n
    brier_baseline_prom = suma_brier_baseline / n
    mejora_pct = ((brier_baseline_prom - brier_modelo_prom) / brier_baseline_prom * 100) if brier_baseline_prom > 0 else 0.0

    por_jornada = [
        {"jornada": j, "brier_promedio": round(suma / cnt, 3)}
        for j, (suma, cnt) in sorted(brier_por_jornada.items())
    ]

    return {
        "n_partidos": n,
        "brier_modelo": round(brier_modelo_prom, 3),
        "brier_baseline": round(brier_baseline_prom, 3),
        "mejora_pct": round(mejora_pct, 1),
        "accuracy_ganador": round(aciertos_ganador / n * 100, 1),
        "por_jornada": por_jornada,
    }
