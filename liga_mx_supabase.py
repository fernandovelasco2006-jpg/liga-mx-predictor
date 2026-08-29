"""
liga_mx_supabase.py — Conexión con Supabase para guardar predicciones y
apuestas del predictor de Liga MX. Mismo patrón que usaste en el
Mundial-predictor, pero apuntando a tablas nuevas (*_ligamx) en un
proyecto de Supabase separado, para no mezclar datos.
"""
import requests
from datetime import datetime, timezone, timedelta
from liga_mx_predictor_skeleton import DATOS_REALES_LIGAMX

TZ_MX = timezone(timedelta(hours=-6))


def _headers(key: str, prefer: str = "return=minimal") -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _id_prediccion(local: str, visit: str, jornada: int) -> str:
    return f"pred_{local}_{visit}_J{jornada}".replace(" ", "_")


def _id_apuesta(local: str, visit: str, jornada: int, indice: int) -> str:
    return f"ap_{local}_{visit}_{indice}_J{jornada}".replace(" ", "_")


def guardar_prediccion(url: str, key: str, local: str, visit: str, jornada: int,
                        r: dict, resultado_real: tuple = None) -> bool:
    """Guarda (o actualiza si ya existe y sigue sin resultado) la
    predicción de un partido. r = salida de simular_partido()."""
    if not (url and key):
        return False
    ahora = datetime.now(TZ_MX)
    gh, ga = resultado_real if resultado_real else (None, None)
    favorito = local if r["prob_home"] > r["prob_away"] else visit
    prob_favorito = max(r["prob_home"], r["prob_away"])

    payload = {
        "id": _id_prediccion(local, visit, jornada),
        "local": local, "visitante": visit, "jornada": jornada,
        "fecha_partido": ahora.strftime("%Y-%m-%d"),
        "guardada_en": ahora.strftime("%Y-%m-%d %H:%M"),
        "prob_local": round(r["prob_home"], 1),
        "prob_empate": round(r["prob_draw"], 1),
        "prob_visitante": round(r["prob_away"], 1),
        "goles_local_esp": round(r["goles_home"], 2),
        "goles_visita_esp": round(r["goles_away"], 2),
        "favorito": favorito,
        "prob_favorito": round(prob_favorito, 1),
        "arbitro": r.get("arbitro", "Sin asignar"),
        "lam_local": r["lam_home"],
        "lam_visitante": r["lam_away"],
        "resultado_real": f"{gh}-{ga}" if gh is not None else None,
        "goles_local": gh, "goles_visitante": ga,
    }
    try:
        chk = requests.get(
            f"{url}/rest/v1/predicciones_ligamx",
            headers=_headers(key, prefer=""),
            params={"id": f"eq.{payload['id']}", "select": "id"},
            timeout=5,
        )
        if chk.status_code == 200 and not chk.json():
            requests.post(f"{url}/rest/v1/predicciones_ligamx", headers=_headers(key), json=payload, timeout=5)
        elif chk.status_code == 200 and chk.json():
            requests.patch(
                f"{url}/rest/v1/predicciones_ligamx",
                headers=_headers(key, prefer=""),
                params={"id": f"eq.{payload['id']}"},
                json=payload, timeout=5,
            )
        return True
    except Exception:
        return False


def guardar_apuestas(url: str, key: str, local: str, visit: str, jornada: int,
                      sugerencias: list, resultado_real: tuple = None) -> int:
    """Guarda las apuestas de nivel ALTA sugeridas para un partido.
    sugerencias = salida de analizar_apuestas()."""
    if not (url and key):
        return 0
    ahora = datetime.now(TZ_MX)
    gh, ga = resultado_real if resultado_real else (None, None)
    guardadas = 0

    for i, s in enumerate(sugerencias):
        if s["nivel"] != "ALTA":
            continue
        acierto = None
        if gh is not None:
            datos = DATOS_REALES_LIGAMX.get(f"{local}_{visit}", {})
            acierto = evaluar_acierto(s, local, visit, gh, ga,
                                       am_reales=datos.get("am"), co_reales=datos.get("co"))
        payload = {
            "id": _id_apuesta(local, visit, jornada, i),
            "local": local, "visitante": visit, "jornada": jornada,
            "fecha_partido": ahora.strftime("%Y-%m-%d"),
            "guardada_en": ahora.strftime("%Y-%m-%d %H:%M"),
            "mercado": s["mercado"],
            "seleccion": s["seleccion"].replace("✅ ", ""),
            "confianza": round(s["confianza"], 1),
            "resultado_real": f"{gh}-{ga}" if gh is not None else None,
            "goles_local": gh, "goles_visitante": ga,
            "acierto": acierto,
        }
        try:
            chk = requests.get(
                f"{url}/rest/v1/apuestas_historial_ligamx",
                headers=_headers(key, prefer=""),
                params={"id": f"eq.{payload['id']}", "select": "id,acierto"},
                timeout=5,
            )
            if chk.status_code == 200 and not chk.json():
                requests.post(f"{url}/rest/v1/apuestas_historial_ligamx", headers=_headers(key), json=payload, timeout=5)
                guardadas += 1
            elif chk.status_code == 200 and chk.json() and chk.json()[0].get("acierto") is None and acierto is not None:
                requests.patch(
                    f"{url}/rest/v1/apuestas_historial_ligamx",
                    headers=_headers(key, prefer=""),
                    params={"id": f"eq.{payload['id']}"},
                    json={"resultado_real": payload["resultado_real"],
                          "goles_local": gh, "goles_visitante": ga, "acierto": acierto},
                    timeout=5,
                )
        except Exception:
            continue
    return guardadas


def evaluar_acierto(apuesta: dict, local: str, visit: str, gh: int, ga: int,
                     am_reales: int = None, co_reales: int = None) -> bool:
    """
    Evalúa si una apuesta acertó, dado el resultado real (gh, ga) y,
    si están disponibles, las tarjetas/córners reales del partido
    (am_reales, co_reales — vienen de DATOS_REALES_LIGAMX).
    Soporta: Resultado (1X2), Doble Oportunidad, Total Goles, Ambos
    Marcan, Tarjetas, Córners.
    Si el mercado es Tarjetas/Córners pero no tenemos el dato real
    todavía, devuelve None (queda "pendiente" hasta que lo agregues a
    DATOS_REALES_LIGAMX).
    """
    mercado = apuesta["mercado"]
    sel = apuesta["seleccion"].replace("✅ ", "")
    goles_totales = gh + ga

    if mercado == "Resultado (1X2)":
        if f"Gana {local}" in sel:
            return gh > ga
        if f"Gana {visit}" in sel:
            return ga > gh
        return None

    if mercado == "Doble Oportunidad":
        if local in sel and "o Empate" in sel:
            return gh >= ga
        if visit in sel and "o Empate" in sel:
            return ga >= gh
        return None

    if mercado == "Total Goles":
        for linea, umbral in [("0.5", 0), ("1.5", 1), ("2.5", 2), ("3.5", 3)]:
            if linea in sel:
                if "Over" in sel:
                    return goles_totales > umbral
                if "Under" in sel:
                    return goles_totales <= umbral
        return None

    if mercado == "Empate Sin Apuesta":
        if gh == ga:
            return None  # empate → se reembolsa el stake, no cuenta como acierto ni fallo
        if local in sel:
            return gh > ga
        if visit in sel:
            return ga > gh
        return None

    if mercado == "Hándicap Asiático":
        if "-1.0" in sel:
            umbral_cubre, umbral_empuje = 2, 1
        elif "-2.0" in sel:
            umbral_cubre, umbral_empuje = 3, 2
        else:
            return None
        if local in sel:
            diferencia = gh - ga
        elif visit in sel:
            diferencia = ga - gh
        else:
            return None
        if diferencia >= umbral_cubre:
            return True
        if diferencia == umbral_empuje:
            return None  # empuje → se reembolsa el stake
        return False

    if mercado == "Ambos Marcan":
        ambos = gh > 0 and ga > 0
        if "Sí" in sel:
            return ambos
        if "No" in sel:
            return not ambos
        return None

    if mercado == "Tarjetas":
        if am_reales is None:
            return None  # sin dato real todavía → pendiente
        for linea, umbral in [("2.5", 2), ("3.5", 3), ("4.5", 4)]:
            if linea in sel:
                if "Over" in sel:
                    return am_reales > umbral
                if "Under" in sel:
                    return am_reales <= umbral
        return None

    if mercado == "Córners":
        if co_reales is None:
            return None  # sin dato real todavía → pendiente
        for linea, umbral in [("6.5", 6), ("7.5", 7), ("8.5", 8), ("9.5", 9)]:
            if linea in sel:
                if "Over" in sel:
                    return co_reales > umbral
                if "Under" in sel:
                    return co_reales <= umbral
        return None

    return None


def cargar_historial_apuestas(url: str, key: str) -> list:
    """Trae todo el historial de apuestas guardadas."""
    if not (url and key):
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/apuestas_historial_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "*", "order": "guardada_en.desc", "limit": 500},
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def cargar_historial_predicciones(url: str, key: str) -> list:
    """
    Trae todo el historial de predicciones 1X2 guardadas (tabla
    predicciones_ligamx) — mismo patrón que cargar_historial_apuestas(),
    pero para las probabilidades crudas de simular_partido() en vez de
    las selecciones de analizar_apuestas(). Es la fuente de datos para
    calcular_brier_score() y calcular_calibracion_por_bin(): ahí es
    donde viven prob_local/prob_empate/prob_visitante junto con
    goles_local/goles_visitante reales una vez jugado el partido.
    """
    if not (url and key):
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/predicciones_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "*", "order": "guardada_en.desc", "limit": 500},
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def calcular_brier_score(historial_predicciones: list) -> dict:
    """
    Brier score multi-clase (1X2) sobre todas las predicciones ya
    evaluadas (con resultado_real != None) en predicciones_ligamx.

    Fórmula estándar para 3 categorías (local/empate/visitante):
        Brier = promedio( (p_local - y_local)² + (p_empate - y_empate)²
                           + (p_visita - y_visita)² )
    donde y_x vale 1 si esa categoría ocurrió y 0 si no. Rango: 0
    (predicciones perfectas) a 2 (el peor caso posible en 3 clases) —
    para referencia, "tirar una moneda pareja entre las 3" (33/33/33
    siempre) da Brier ≈ 0.667, así que cualquier valor claramente por
    debajo de eso indica que el modelo aporta información real y no
    solo ruido con forma de porcentaje.

    Nota de tipos: Supabase/PostgREST devuelve las columnas numeric
    (prob_local, prob_empate, prob_visitante) como STRING en el JSON
    ("34.5", no 34.5) — cada valor se convierte con float() antes de
    operar; una fila con un valor no convertible se descarta en vez de
    tronar toda la función.

    Devuelve también el desglose de Brier POR EQUIPO (como local y como
    visitante por separado) para detectar si el modelo está mal
    calibrado específicamente para algunos equipos — insumo directo
    para la futura corrección de sesgo por equipo (ver
    calcular_sesgo_por_equipo(), pendiente de construir cuando haya más
    historial evaluado).
    """
    evaluadas = [
        p for p in historial_predicciones
        if p.get("goles_local") is not None and p.get("goles_visitante") is not None
        and p.get("prob_local") is not None
    ]
    if not evaluadas:
        return {"brier": None, "n_evaluadas": 0, "por_equipo": []}

    suma_brier = 0.0
    n_validas = 0
    brier_por_equipo = {}  # equipo -> [suma_brier, n]

    for p in evaluadas:
        try:
            gh, ga = int(p["goles_local"]), int(p["goles_visitante"])
            p_local = float(p["prob_local"]) / 100.0
            p_empate = float(p["prob_empate"]) / 100.0
            p_visita = float(p["prob_visitante"]) / 100.0
        except (TypeError, ValueError):
            continue  # fila con dato faltante/corrupto — se omite, no tumba el cálculo

        y_local = 1.0 if gh > ga else 0.0
        y_empate = 1.0 if gh == ga else 0.0
        y_visita = 1.0 if gh < ga else 0.0

        brier_partido = (p_local - y_local) ** 2 + (p_empate - y_empate) ** 2 + (p_visita - y_visita) ** 2
        suma_brier += brier_partido
        n_validas += 1

        for equipo in (p["local"], p["visitante"]):
            if equipo not in brier_por_equipo:
                brier_por_equipo[equipo] = [0.0, 0]
            brier_por_equipo[equipo][0] += brier_partido
            brier_por_equipo[equipo][1] += 1

    if n_validas == 0:
        return {"brier": None, "n_evaluadas": 0, "por_equipo": []}

    por_equipo = [
        {"equipo": eq, "brier_promedio": round(suma / n, 3), "n_partidos": n}
        for eq, (suma, n) in brier_por_equipo.items()
    ]
    por_equipo.sort(key=lambda f: f["brier_promedio"], reverse=True)

    return {
        "brier": round(suma_brier / n_validas, 3),
        "n_evaluadas": n_validas,
        "por_equipo": por_equipo,
    }


def calcular_calibracion_por_bin(historial_predicciones: list, ancho_bin: int = 10) -> list:
    """
    Panel de calibración: agrupa TODAS las probabilidades emitidas por
    el modelo (una entrada por cada una de las 3 categorías —
    local/empate/visitante— de cada predicción evaluada) en bins de
    ancho `ancho_bin` (10 puntos por defecto: 50-60%, 60-70%, etc.) y
    compara, dentro de cada bin, el promedio de probabilidad prometida
    contra la frecuencia real con la que esa categoría ocurrió.

    Esto responde la pregunta de fondo de calibración: "de todas las
    veces que el modelo dijo, por ejemplo, 70-80% de confianza en algo,
    ¿de verdad ocurrió ~70-80% de las veces?" — si un bin muestra
    prometido=75% pero real=50%, el modelo está siendo overconfident
    justo en ese rango, y es evidencia dura y accionable (más que solo
    un Brier score global) para decidir, por ejemplo, subir
    UMBRAL_MIN_RECOMENDACION en liga_mx_algoritmo.py.

    Solo incluye bins con al menos 3 observaciones — con menos, el
    porcentaje "real" es demasiado ruidoso para decir algo.
    """
    evaluadas = [
        p for p in historial_predicciones
        if p.get("goles_local") is not None and p.get("goles_visitante") is not None
        and p.get("prob_local") is not None
    ]

    observaciones = []  # (prob_prometida, ocurrio: bool)
    for p in evaluadas:
        try:
            gh, ga = int(p["goles_local"]), int(p["goles_visitante"])
            p_local = float(p["prob_local"])
            p_empate = float(p["prob_empate"])
            p_visita = float(p["prob_visitante"])
        except (TypeError, ValueError):
            continue  # fila con dato faltante/corrupto — se omite
        observaciones.append((p_local, gh > ga))
        observaciones.append((p_empate, gh == ga))
        observaciones.append((p_visita, gh < ga))

    bins = {}
    for prob, ocurrio in observaciones:
        techo_bin = min(int(prob // ancho_bin) * ancho_bin + ancho_bin, 100)
        piso_bin = techo_bin - ancho_bin
        clave = (piso_bin, techo_bin)
        if clave not in bins:
            bins[clave] = {"suma_prometida": 0.0, "n_ocurrio": 0, "n_total": 0}
        bins[clave]["suma_prometida"] += prob
        bins[clave]["n_total"] += 1
        if ocurrio:
            bins[clave]["n_ocurrio"] += 1

    filas = []
    for (piso, techo), datos in sorted(bins.items()):
        if datos["n_total"] < 3:
            continue
        prometido = datos["suma_prometida"] / datos["n_total"]
        real = datos["n_ocurrio"] / datos["n_total"] * 100
        filas.append({
            "rango": f"{piso}-{techo}%",
            "prometido_promedio": round(prometido, 1),
            "real_pct": round(real, 1),
            "brecha": round(prometido - real, 1),
            "n_observaciones": datos["n_total"],
        })

    return filas


PJ_MINIMO_SESGO_EQUIPO = 8  # partidos evaluados mínimo por equipo/rol antes de corregir sesgo
TOPE_CORRECCION_SESGO = 0.15  # ±15% máx — mismo espíritu de tope que el resto del modelo


def calcular_sesgo_por_equipo(historial_predicciones: list,
                               pj_minimo: int = PJ_MINIMO_SESGO_EQUIPO,
                               tope: float = TOPE_CORRECCION_SESGO) -> dict:
    """
    Compara, para cada equipo, cuánto esperaba el modelo que anotara
    (goles_local_esp / goles_visita_esp, guardados en
    predicciones_ligamx por guardar_prediccion()) contra cuánto anotó
    de verdad (goles_local / goles_visitante) — SEPARADO por rol (local
    vs. visitante), porque un equipo puede estar sobreestimado jugando
    en casa y subestimado de visita al mismo tiempo, son sesgos
    independientes.

    Solo devuelve corrección para equipos/rol con pj_minimo (8 por
    defecto) partidos evaluados o más — con menos muestra, la
    diferencia observada es ruido, no señal, y aplicarla metería más
    error del que corrige (el mismo criterio de minimo_evaluadas que ya
    usa calcular_stats_por_mercado(), aquí más estricto porque el
    número que se ajusta —FUERZA_ATAQUE/DEFENSA— alimenta directamente
    a calcular_lambdas() de TODOS los partidos futuros de ese equipo).

    Nota de tipos: igual que calcular_brier_score(), convierte con
    float() cada valor (Supabase/PostgREST los entrega como string) y
    descarta filas con datos faltantes/corruptos en vez de tronar.

    Devuelve:
        {
          "America": {
              "factor_ataque_local": 1.08,   # >1 = anotó más de lo esperado de local
              "factor_ataque_visita": 0.94,  # <1 = anotó menos de lo esperado de visita
              "pj_local": 9, "pj_visita": 8,
          },
          ...
        }
    Solo incluye equipos con al menos un rol (local o visita) que
    alcanzó pj_minimo — los que no, simplemente no aparecen en el
    diccionario, y el llamador (calcular_lambdas()) debe tratar la
    ausencia como "sin corrección" (factor 1.0), nunca como error.
    """
    # acumuladores separados por rol: equipo -> [suma_esp, suma_real, n]
    local_stats = {}
    visita_stats = {}

    for p in historial_predicciones:
        if p.get("goles_local") is None or p.get("goles_visitante") is None:
            continue
        try:
            gh, ga = int(p["goles_local"]), int(p["goles_visitante"])
            esp_local = float(p["goles_local_esp"])
            esp_visita = float(p["goles_visita_esp"])
        except (TypeError, ValueError, KeyError):
            continue

        local = p.get("local")
        visit = p.get("visitante")
        if not local or not visit:
            continue

        if local not in local_stats:
            local_stats[local] = [0.0, 0, 0]
        local_stats[local][0] += esp_local
        local_stats[local][1] += gh
        local_stats[local][2] += 1

        if visit not in visita_stats:
            visita_stats[visit] = [0.0, 0, 0]
        visita_stats[visit][0] += esp_visita
        visita_stats[visit][1] += ga
        visita_stats[visit][2] += 1

    resultado = {}
    equipos = set(local_stats) | set(visita_stats)
    for equipo in equipos:
        entrada = {}
        if equipo in local_stats:
            suma_esp, suma_real, n = local_stats[equipo]
            if n >= pj_minimo and suma_esp > 0:
                razon = suma_real / suma_esp
                entrada["factor_ataque_local"] = max(1 - tope, min(1 + tope, razon))
                entrada["pj_local"] = n
        if equipo in visita_stats:
            suma_esp, suma_real, n = visita_stats[equipo]
            if n >= pj_minimo and suma_esp > 0:
                razon = suma_real / suma_esp
                entrada["factor_ataque_visita"] = max(1 - tope, min(1 + tope, razon))
                entrada["pj_visita"] = n
        if entrada:
            resultado[equipo] = entrada

    return resultado


def calcular_stats_apuestas(historial: list) -> dict:
    evaluadas = [a for a in historial if a.get("acierto") is not None]
    pendientes = [a for a in historial if a.get("acierto") is None]
    aciertos = [a for a in evaluadas if a["acierto"]]
    fallos = [a for a in evaluadas if not a["acierto"]]
    accuracy = (len(aciertos) / len(evaluadas) * 100) if evaluadas else 0.0
    return {
        "accuracy": accuracy,
        "aciertos": len(aciertos),
        "fallos": len(fallos),
        "total_evaluadas": len(evaluadas),
        "total_pendientes": len(pendientes),
        "evaluadas": evaluadas,
        "pendientes": pendientes,
    }


def calcular_stats_por_mercado(historial: list, minimo_evaluadas: int = 3) -> list:
    """
    Panel de auto-calibración: compara, mercado por mercado, la confianza
    que dijo el modelo (promedio de "confianza" al momento de sugerir la
    apuesta) contra el acierto REAL una vez que el partido ya se jugó.

    Si el modelo está bien calibrado, "confianza promedio" y "acierto
    real" deberían andar parecidos (ej. dice 85% y acierta ~85% de las
    veces). Si un mercado acierta bastante MENOS de lo que dice, es señal
    de que ese mercado específico está sobre-confiado y su umbral (o su
    fórmula) debería revisarse; si acierta MÁS de lo que dice, el modelo
    se está quedando corto ahí y hay margen para bajar el umbral con
    confianza.

    minimo_evaluadas: no se reporta un mercado hasta que tenga al menos
    este número de apuestas YA evaluadas (con resultado real) — con
    1-2 casos la tasa de acierto no dice nada todavía, es puro ruido.

    Devuelve una lista de dicts, uno por mercado, ordenada de mayor a
    menor "brecha" (|confianza_promedio - accuracy_real|) — así lo
    primero que se ve es el mercado que más se aleja de lo prometido.
    """
    por_mercado = {}
    for a in historial:
        merc = a.get("mercado", "Desconocido")
        por_mercado.setdefault(merc, []).append(a)

    filas = []
    for merc, apuestas_merc in por_mercado.items():
        evaluadas = [a for a in apuestas_merc if a.get("acierto") is not None]
        pendientes = [a for a in apuestas_merc if a.get("acierto") is None]
        if len(evaluadas) < minimo_evaluadas:
            continue
        aciertos = [a for a in evaluadas if a["acierto"]]
        accuracy_real = len(aciertos) / len(evaluadas) * 100
        confianza_promedio = sum(a.get("confianza", 0) for a in evaluadas) / len(evaluadas)
        brecha = confianza_promedio - accuracy_real
        if brecha > 5:
            diagnostico = "⚠️ Sobre-confiado — acierta menos de lo que dice"
        elif brecha < -5:
            diagnostico = "📈 Conservador — acierta más de lo que dice"
        else:
            diagnostico = "✅ Bien calibrado"
        filas.append({
            "mercado": merc,
            "n_evaluadas": len(evaluadas),
            "n_pendientes": len(pendientes),
            "aciertos": len(aciertos),
            "fallos": len(evaluadas) - len(aciertos),
            "accuracy_real": round(accuracy_real, 1),
            "confianza_promedio": round(confianza_promedio, 1),
            "brecha": round(brecha, 1),
            "diagnostico": diagnostico,
        })

    filas.sort(key=lambda f: abs(f["brecha"]), reverse=True)
    return filas


def calcular_mercados_suspendidos(historial: list, minimo_evaluadas: int = 5,
                                   piso_accuracy: float = 65.0, brecha_maxima: float = 15.0) -> set:
    """
    RETROALIMENTACIÓN AUTOMÁTICA: decide qué mercados debe DEJAR de
    sugerir el modelo por el momento, usando el mismo panel de
    auto-calibración (calcular_stats_por_mercado) pero convertido en una
    regla accionable en vez de solo un reporte para leer.

    Un mercado se suspende si, con al menos `minimo_evaluadas` apuestas
    YA evaluadas (resultado real conocido):
      - su acierto real cae por debajo de `piso_accuracy` (65% por
        defecto — un mercado que decía 80%+ pero acierta menos de 65%
        de las veces está claramente mal calibrado, no es solo mala
        suerte), O
      - la brecha entre lo que prometió y lo que cumplió supera
        `brecha_maxima` puntos (15 por defecto).

    minimo_evaluadas=5 aquí es MÁS ALTO que el 3 que usa el panel
    informativo — suspender un mercado es una decisión con consecuencia
    real (deja de aparecer en apuestas sugeridas), así que pide más
    evidencia antes de actuar que solo mostrar un número en un reporte.

    CLAVE: esto se recalcula desde cero cada vez que se llama, nunca
    queda un mercado "marcado" de forma permanente. En cuanto entren más
    resultados y el acierto real se recupere por encima del piso, el
    mercado se vuelve a sugerir automáticamente solo, sin tocar código.
    """
    stats = calcular_stats_por_mercado(historial, minimo_evaluadas=minimo_evaluadas)
    suspendidos = set()
    for fm in stats:
        if fm["accuracy_real"] < piso_accuracy or fm["brecha"] > brecha_maxima:
            suspendidos.add(fm["mercado"])
    return suspendidos


def guardar_parlay_diario(url: str, key: str, fecha: str, selecciones: list, prob_combinada: float) -> bool:
    """
    Guarda EL parlay del día (una sola fila por fecha) combinando la
    mejor apuesta de cada partido del día. selecciones = lista de dicts
    con local, visitante, jornada, mercado, seleccion, confianza.
    """
    if not (url and key) or len(selecciones) < 2:
        return False
    ahora = datetime.now(TZ_MX)
    parlay_id = f"parlay_{fecha}"
    payload = {
        "id": parlay_id,
        "fecha": fecha,
        "creado_en": ahora.strftime("%Y-%m-%d %H:%M"),
        "selecciones": selecciones,
        "prob_combinada": round(prob_combinada, 1),
        "n_partidos": len(selecciones),
        "resultado": "pendiente",
    }
    try:
        chk = requests.get(
            f"{url}/rest/v1/parlays_historial_ligamx",
            headers=_headers(key, prefer=""),
            params={"id": f"eq.{parlay_id}", "select": "id"},
            timeout=5,
        )
        if chk.status_code == 200 and not chk.json():
            requests.post(f"{url}/rest/v1/parlays_historial_ligamx", headers=_headers(key), json=payload, timeout=5)
            return True
    except Exception:
        pass
    return False


def cargar_historial_parlays(url: str, key: str) -> list:
    """Trae todos los parlays diarios guardados, más recientes primero."""
    if not (url and key):
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/parlays_historial_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "*", "order": "fecha.desc", "limit": 200},
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def actualizar_parlays_pendientes(url: str, key: str, partidos_jugados: list) -> int:
    """
    Revisa cada parlay pendiente: si TODAS sus patas ya tienen
    resultado real, evalúa cada una y marca el parlay completo como
    'ganado' (si todas acertaron) o 'perdido' (si al menos una falló).
    Si falta el resultado de algún partido de la pata, o falta el dato
    real de tarjetas/córners para evaluar esa pata, se queda pendiente.
    """
    if not (url and key):
        return 0
    mapa_resultados = {(local, visit): res for local, visit, jornada, estadio, res, arb in partidos_jugados}

    try:
        resp = requests.get(
            f"{url}/rest/v1/parlays_historial_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "*", "resultado": "eq.pendiente", "limit": 100},
            timeout=10,
        )
        pendientes = resp.json() if resp.status_code == 200 else []
    except Exception:
        return 0

    actualizados = 0
    for parlay in pendientes:
        selecciones = parlay.get("selecciones", [])
        if isinstance(selecciones, str):
            import json as _json
            try:
                selecciones = _json.loads(selecciones)
            except Exception:
                continue

        estados = []
        for sel in selecciones:
            clave = (sel.get("local"), sel.get("visitante"))
            resultado = mapa_resultados.get(clave)
            if resultado is None:
                estados.append(None)
                continue
            gh, ga = resultado
            datos = DATOS_REALES_LIGAMX.get(f"{sel.get('local')}_{sel.get('visitante')}", {})
            acierto = evaluar_acierto(sel, sel.get("local"), sel.get("visitante"), gh, ga,
                                       am_reales=datos.get("am"), co_reales=datos.get("co"))
            estados.append(acierto)

        if any(e is False for e in estados):
            nuevo_resultado = "perdido"
        elif estados and all(e is True for e in estados):
            nuevo_resultado = "ganado"
        else:
            continue  # sigue pendiente

        try:
            requests.patch(
                f"{url}/rest/v1/parlays_historial_ligamx",
                headers=_headers(key, prefer=""),
                params={"id": f"eq.{parlay['id']}"},
                json={"resultado": nuevo_resultado},
                timeout=8,
            )
            actualizados += 1
        except Exception:
            continue
    return actualizados


def guardar_jornada_completa(url: str, key: str, resultado_simulacion: dict) -> dict:
    """
    Guarda en el historial TODOS los partidos que vienen en el paquete
    devuelto por liga_mx_algoritmo.simular_jornada_completa() — un
    guardar_prediccion() + guardar_apuestas() por partido, reutilizando
    exactamente las mismas funciones (y por lo tanto el mismo formato de
    fila) que ya usa el flujo de "un partido a la vez".

    No introduce ninguna tabla ni columna nueva: es un for-loop sobre
    partidos que llama a lo que ya existe, así que
    calcular_mercados_suspendidos() y el resto del panel de
    auto-calibración funcionan sin cambios sobre estas filas.

    resultado_simulacion = salida de simular_jornada_completa().

    Devuelve un resumen para mostrar en la interfaz:
        {
          "jornada": int,
          "partidos_guardados": int,
          "apuestas_guardadas": int,
          "errores": [str, ...],   # local-visitante que fallaron al guardar
        }
    """
    jornada = resultado_simulacion.get("jornada")
    partidos = resultado_simulacion.get("partidos", [])

    resumen = {"jornada": jornada, "partidos_guardados": 0, "apuestas_guardadas": 0, "errores": []}
    if jornada is None or not (url and key):
        return resumen

    for p in partidos:
        local, visit = p["local"], p["visitante"]
        r = p["resultado_sim"]
        apuestas = p["apuestas"]
        try:
            ok_pred = guardar_prediccion(url, key, local, visit, jornada, r)
            n_ap = guardar_apuestas(url, key, local, visit, jornada, apuestas)
            if ok_pred:
                resumen["partidos_guardados"] += 1
            resumen["apuestas_guardadas"] += n_ap
        except Exception as e:
            resumen["errores"].append(f"{local}-{visit}: {e}")

    return resumen

    """
    Recorre PARTIDOS ya jugados y actualiza el campo 'acierto' de
    cualquier apuesta guardada que siga pendiente (acierto=null).
    partidos_jugados = [(local, visit, jornada, estadio, (gh,ga), arbitro), ...]
    """
    if not (url and key):
        return 0
    mapa_resultados = {(local, visit): res for local, visit, jornada, estadio, res, arb in partidos_jugados}

    try:
        resp = requests.get(
            f"{url}/rest/v1/apuestas_historial_ligamx",
            headers=_headers(key, prefer=""),
            params={"select": "*", "acierto": "is.null", "limit": 500},
            timeout=10,
        )
        pendientes = resp.json() if resp.status_code == 200 else []
    except Exception:
        return 0

    actualizadas = 0
    for ap in pendientes:
        clave = (ap["local"], ap["visitante"])
        resultado = mapa_resultados.get(clave)
        if resultado is None:
            continue
        gh, ga = resultado
        datos = DATOS_REALES_LIGAMX.get(f"{ap['local']}_{ap['visitante']}", {})
        acierto = evaluar_acierto(ap, ap["local"], ap["visitante"], gh, ga,
                                   am_reales=datos.get("am"), co_reales=datos.get("co"))
        if acierto is None:
            continue
        try:
            requests.patch(
                f"{url}/rest/v1/apuestas_historial_ligamx",
                headers=_headers(key, prefer=""),
                params={"id": f"eq.{ap['id']}"},
                json={"resultado_real": f"{gh}-{ga}", "goles_local": gh,
                      "goles_visitante": ga, "acierto": acierto},
                timeout=8,
            )
            actualizadas += 1
        except Exception:
            continue
    return actualizadas
