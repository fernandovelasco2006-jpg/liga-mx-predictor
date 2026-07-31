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


def actualizar_aciertos_pendientes(url: str, key: str, partidos_jugados: list) -> int:
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
