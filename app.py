import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, timezone

from liga_mx_predictor_skeleton import (
    EQUIPOS, ALTITUD_EQUIPO, PARTIDOS, HORARIOS_PARTIDO, ARBITROS_LIGA_MX,
    ARBITRO_DEFAULT, CORNERS_EQUIPO,
)
from liga_mx_algoritmo import (
    calcular_lambdas, simular_temporada, simular_temporada_montecarlo,
    simular_partido, analizar_apuestas, armar_parlay, tabla_actual_real,
    ALTITUD_UMBRAL, BONUS_ALTITUD_LOCAL, FACTOR_FATIGA_LEAGUES_CUP,
    PROMEDIO_LIGA_AMARILLAS, PROMEDIO_LIGA_ROJAS,
    ELO_BASE, ELO_ACTUALIZADO, resumen_movimiento_elo, n_partidos_procesados,
    simular_jornada_completa, detectar_jornada_actual, armar_super_parlay_jornada,
)

try:
    from liga_mx_supabase import (
        guardar_prediccion, guardar_apuestas, cargar_historial_apuestas,
        calcular_stats_apuestas, calcular_stats_por_mercado, calcular_mercados_suspendidos,
        actualizar_aciertos_pendientes,
        guardar_parlay_diario, cargar_historial_parlays, actualizar_parlays_pendientes,
        cargar_historial_predicciones, calcular_brier_score, calcular_calibracion_por_bin,
        calcular_sesgo_por_equipo, guardar_jornada_completa,
    )
    SUPABASE_MODULO_DISPONIBLE = True
except ImportError:
    SUPABASE_MODULO_DISPONIBLE = False

try:
    from liga_mx_clima import obtener_clima_partido, factor_clima as _calc_factor_clima
    CLIMA_MODULO_DISPONIBLE = True
except ImportError:
    CLIMA_MODULO_DISPONIBLE = False

try:
    from liga_mx_cuotas import obtener_cuotas_jornada
    CUOTAS_MODULO_DISPONIBLE = True
except ImportError:
    CUOTAS_MODULO_DISPONIBLE = False

try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL_LIGAMX", None)
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY_LIGAMX", None)
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL_LIGAMX", None)
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LIGAMX", None)

try:
    WEATHER_API_KEY = st.secrets.get("WEATHER_API_KEY", None)
except Exception:
    WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", None)

try:
    ODDS_API_KEY = st.secrets.get("ODDS_API_KEY", None)
except Exception:
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", None)

SUPABASE_DISPONIBLE = SUPABASE_MODULO_DISPONIBLE and SUPABASE_URL and SUPABASE_KEY

st.set_page_config(
    page_title="Liga MX · Apertura 2026 · Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────
# PESOS DEL MODELO — fijos en el código, no ajustables desde la interfaz.
# Si algún día quieres recalibrar, cámbialos aquí (no en la UI).
# ─────────────────────────────────────────────────────────────────────────
PESO_ELO = 1.0
PESO_ALTITUD = 1.0
PESO_ARBITRO = 1.0
N_SIMS_PARTIDO = 10_000_000

# ─────────────────────────────────────────────────────────────────────────
# ESTILO — mismo lenguaje visual que el Mundial-predictor: verde/blanco/
# rojo (México) + magenta Liga MX como acento.
# ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Bebas Neue', sans-serif; letter-spacing: 2px; }
.stApp { background: #0a1410; color: #e8f0ea; }
.block-container { padding: 2rem 2rem 4rem; max-width: 1100px; }
.hero { background: linear-gradient(135deg, #0d2818 0%, #1a2e1f 40%, #2a0d14 100%); border: 1px solid #1f4a2e; border-radius: 16px; padding: 2rem 2.5rem; margin-bottom: 2rem; position: relative; overflow: hidden; }
.hero::before { content: "⚽"; position: absolute; right: 2rem; top: 50%; transform: translateY(-50%); font-size: 5rem; opacity: 0.07; }
.hero-title { font-family: 'Bebas Neue', sans-serif; font-size: 3rem; letter-spacing: 4px; color: #e5007d; margin: 0; line-height: 1; }
.hero-sub { color: #8fbfa0; font-size: 0.8rem; margin-top: 0.4rem; letter-spacing: 1px; text-transform: uppercase; }
.prob-bar { display:flex; height:12px; border-radius:6px; overflow:hidden; margin:0.75rem 0; }
.bar-a { background:#006341; } .bar-draw { background:#4b5563; } .bar-b { background:#CE1126; }
.result-box { background: linear-gradient(135deg, #0d2818, #1a2e1f); border: 1px solid #1f4a2e; border-radius: 14px; padding: 1.5rem 1rem; text-align: center; }
.result-box-draw { border-color: #374151; } .result-box-b { border-color: #4a1f26; }
.team-name { font-family: 'Bebas Neue', sans-serif; font-size: 1.3rem; letter-spacing: 2px; color: #e8f0ea; margin: 0.2rem 0; }
.prob-pct { font-family: 'Bebas Neue', sans-serif; font-size: 3rem; line-height:1; color: #4ade80; }
.prob-pct-b { color: #f87171; } .prob-pct-draw { color: #9ca3af; }
.prob-lbl { font-size: 0.6rem; color: #6b9b7d; letter-spacing: 2px; text-transform: uppercase; }
.goles-esp { font-family: 'Bebas Neue', sans-serif; font-size: 1.6rem; color: #e5007d; }
.score-badge { display:inline-block; background:#12241a; border:1px solid #1f4a2e; border-radius:8px; padding:0.3rem 0.9rem; margin:0.15rem; font-family:'Bebas Neue', sans-serif; font-size:1.1rem; color:#e8f0ea; text-align:center; }
.score-badge-top { background:#2a0d1a; border-color:#e5007d; color:#e5007d; }
.tag { display:inline-block; border-radius:20px; padding:2px 10px; font-size:0.65rem; letter-spacing:1px; text-transform:uppercase; margin-right:0.4rem; }
.tag-played  { background:#1a3a2a; color:#4ade80; border:1px solid #2d6b45; }
.tag-pending { background:#2a0d1a; color:#e5007d; border:1px solid #5a1a3a; }
.metric-box { background:#0f1e15; border:1px solid #1f4a2e; border-radius:10px; padding:0.9rem; text-align:center; }
.metric-val { font-family:'Bebas Neue',sans-serif; font-size:2rem; color:#e5007d; line-height:1; }
.metric-lbl { font-size:0.6rem; color:#6b9b7d; letter-spacing:1px; text-transform:uppercase; margin-top:0.2rem; }
.model-note { background:#0d1a12; border-left:3px solid #006341; border-radius:0 8px 8px 0; padding:0.7rem 1rem; font-size:0.75rem; color:#8fbfa0; margin-top:1.2rem; }
.bet-card { border-radius:10px; padding:0.9rem; height:100%; }
.bet-card-alta { background:#0d2818; border:1px solid #2d6b45; }
.value-bet-badge { display:inline-block; background:linear-gradient(135deg,#3a2a00,#5a4000); border:1px solid #f0c040; color:#f0c040; border-radius:6px; padding:1px 8px; font-size:0.58rem; letter-spacing:1px; text-transform:uppercase; margin-top:0.3rem; font-weight:600; }
.no-apostable-badge { display:inline-block; background:#2a2018; border:1px solid #6b5a3a; color:#b8a67a; border-radius:6px; padding:1px 8px; font-size:0.58rem; letter-spacing:0.5px; margin-top:0.3rem; font-weight:500; }
.bet-card-media { background:#12241a; border:1px solid #1f4a2e; }
.parlay-card { background:linear-gradient(135deg,#1a1500,#2a2000); border:1px solid #e5007d; border-radius:10px; padding:0.8rem 1rem; margin-top:0.75rem; }
.disclaimer-banner { background: linear-gradient(135deg, #2a1500, #3a1e00); border: 1px solid #5a3a00; border-radius: 10px; padding: 0.7rem 1.2rem; margin-bottom: 1rem; font-size: 0.75rem; color: #f0c040; line-height: 1.5; text-align: center; }
.stButton > button { background: linear-gradient(135deg,#006341,#e5007d) !important; font-size:1rem !important; color:white !important; border:none !important; border-radius:8px !important; font-family:'Bebas Neue', sans-serif !important; letter-spacing:2px !important; padding:0.6rem 2rem !important; width:100% !important; }
.stButton > button:hover { filter: brightness(1.15); }
.stSelectbox > div > div { background:#0f1e15 !important; border:1px solid #1f4a2e !important; color:#e8f0ea !important; border-radius:8px !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer-banner">
⚠️ <b>Aviso legal:</b> Proyecto independiente, sin fines de lucro, de carácter educativo/informativo.
Las predicciones se generan por simulación estadística (Monte Carlo) y <b>no constituyen asesoría de apuestas ni garantía de resultados</b>.
Apuesta responsablemente y solo en plataformas legales. Debes ser mayor de edad (18+).
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="hero-title">LIGA MX · APERTURA 2026</div>
  <div class="hero-sub">Monte Carlo · 10,000,000 simulaciones · ELO + Altitud + Árbitro + Clima</div>
</div>""", unsafe_allow_html=True)

BANDERAS_EQUIPO = {
    "America": "🦅", "Atlante": "🐎", "Atlas": "🦊", "Atletico San Luis": "🐶",
    "Cruz Azul": "🚂", "Guadalajara": "🐐", "FC Juarez": "🐴", "Leon": "🦁",
    "Monterrey": "🤠", "Necaxa": "⚡", "Pachuca": "🐹", "Puebla": "🎽",
    "Pumas UNAM": "🐾", "Queretaro": "🐔", "Santos Laguna": "⚔️",
    "Tijuana": "🐕", "Tigres": "🐯", "Toluca": "👹",
}

def flag(t):
    return BANDERAS_EQUIPO.get(t, "⚽")

def tag(cls, txt):
    return f'<span class="tag {cls}">{txt}</span>'


def _badge_value_bet(ap: dict) -> str:
    """
    HTML del badge "💰 VALUE BET" para una apuesta, si trae value_bet
    con tiene_valor=True (ver liga_mx_algoritmo.analizar_apuestas() y
    liga_mx_cuotas.calcular_value_bet()). Cadena vacía si no aplica —
    ninguna cuota disponible, o el EV no superó el umbral configurado en
    liga_mx_cuotas.UMBRAL_VALUE_EV — para poder insertarlo directo en
    cualquier f-string de tarjeta sin condicionales repetidos.
    """
    vb = ap.get("value_bet")
    if not vb or not vb.get("tiene_valor"):
        return ""
    ev = vb.get("ev_pct")
    return f'<div class="value-bet-badge">💰 Value Bet · EV +{ev:.1f}%</div>'


def _badge_no_apostable(ap: dict) -> str:
    """
    HTML del badge "⚠️ No apostable" — QUEDÓ SIN EFECTO PRÁCTICO por
    decisión posterior del usuario: liga_mx_algoritmo.analizar_apuestas()
    ahora DESCARTA por completo (no la agrega a la lista de sugerencias)
    cualquier línea de Total de Goles que ninguna casa real ofrezca,
    en vez de incluirla marcada con "no_apostable": True como antes.

    Esta función se deja intacta (no se elimina del código ni de las
    tarjetas que la llaman) por si en el futuro se prefiere volver al
    comportamiento anterior de "mostrar con advertencia" — hoy nunca
    encuentra "no_apostable" en una apuesta (esas simplemente no
    llegan aquí) y siempre devuelve cadena vacía.
    """
    if not ap.get("no_apostable"):
        return ""
    return '<div class="no-apostable-badge">⚠️ Sin cuota real disponible</div>'

if "historial_apuestas_sesion" not in st.session_state:
    st.session_state["historial_apuestas_sesion"] = []

def _registrar_apuestas_sesion(local, visit, jornada, sugs, r=None, resultado_real=None):
    ya_registrado = any(
        h["local"] == local and h["visit"] == visit for h in st.session_state["historial_apuestas_sesion"]
    )
    if not ya_registrado:
        for s in sugs:
            if s["nivel"] != "ALTA":
                continue
            st.session_state["historial_apuestas_sesion"].append({
                "local": local, "visit": visit, "jornada": jornada,
                "mercado": s["mercado"], "seleccion": s["seleccion"], "confianza": s["confianza"],
                "hora_registro": datetime.now().strftime("%H:%M:%S"),
            })

    # Persistencia real en Supabase (si está conectado)
    if SUPABASE_DISPONIBLE:
        try:
            if r is not None:
                guardar_prediccion(SUPABASE_URL, SUPABASE_KEY, local, visit, jornada, r, resultado_real)
            guardar_apuestas(SUPABASE_URL, SUPABASE_KEY, local, visit, jornada, sugs, resultado_real)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────────────
# TABS — misma barra que el Mundial-predictor
# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# Auto-actualizar aciertos pendientes contra resultados reales (1 vez
# por sesión, igual patrón que el Mundial-predictor)
# ─────────────────────────────────────────────────────────────────────────
if SUPABASE_DISPONIBLE and not st.session_state.get("aciertos_lm_actualizados"):
    partidos_jugados = [p for p in PARTIDOS if p[4] is not None]
    if partidos_jugados:
        try:
            actualizar_aciertos_pendientes(SUPABASE_URL, SUPABASE_KEY, partidos_jugados)
            actualizar_parlays_pendientes(SUPABASE_URL, SUPABASE_KEY, partidos_jugados)
        except Exception:
            pass
    st.session_state["aciertos_lm_actualizados"] = True


# ─────────────────────────────────────────────────────────────────────────
# APUESTAS MÁS FUERTES DE HOY — arriba de todo, se calcula solo al abrir
# la página. Cacheado 1 hora para no re-simular 10M por cada visitante.
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _simular_partido_cached(local, visit, n, peso_elo, peso_altitud, peso_arbitro, factor_clima=1.0):
    # Nota: el sesgo por equipo (_sesgo_equipo_cached, TTL 15 min) se lee
    # aquí dentro de una función cacheada por 1 hora — si el sesgo cambia
    # a mitad de esa hora (un equipo cruza el umbral de 8 PJ evaluados),
    # este resultado sigue sirviendo la versión vieja hasta que expire el
    # caché de 1 hora. Aceptable: el sesgo por equipo cambia jornada a
    # jornada, no dentro de la misma hora.
    return simular_partido(local, visit, n=n, peso_elo=peso_elo,
                            peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
                            factor_clima=factor_clima, sesgo_por_equipo=_sesgo_equipo_cached())


# ─────────────────────────────────────────────────────────────────────────
# RETROALIMENTACIÓN AUTOMÁTICA — trae el historial de apuestas y calcula
# qué mercados (si alguno) hay que dejar de sugerir por bajo acierto
# real. Cacheado 15 min (más corto que las simulaciones: esto sí cambia
# seguido conforme se van evaluando apuestas nuevas jornada a jornada).
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def _mercados_suspendidos_cached():
    if not SUPABASE_MODULO_DISPONIBLE or not (SUPABASE_URL and SUPABASE_KEY):
        return frozenset()
    historial = cargar_historial_apuestas(SUPABASE_URL, SUPABASE_KEY)
    return frozenset(calcular_mercados_suspendidos(historial))


# ─────────────────────────────────────────────────────────────────────────
# CORRECCIÓN DE SESGO POR EQUIPO — retroalimentación real: compara,
# equipo por equipo (separado por rol local/visita), los goles esperados
# que el modelo guardó en predicciones_ligamx contra los que anotó de
# verdad, y devuelve un factor de ajuste acotado (±15%) sólo para
# equipos con 8+ partidos evaluados en ese rol. Cacheado 15 min, mismo
# TTL que _mercados_suspendidos_cached() por el mismo motivo: cambia
# conforme se evalúan apuestas jornada a jornada, no de un minuto a otro.
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def _sesgo_equipo_cached():
    if not SUPABASE_MODULO_DISPONIBLE or not (SUPABASE_URL and SUPABASE_KEY):
        return {}
    historial_pred = cargar_historial_predicciones(SUPABASE_URL, SUPABASE_KEY)
    return calcular_sesgo_por_equipo(historial_pred)


# ─────────────────────────────────────────────────────────────────────────
# CLIMA — temperatura/humedad/lluvia del partido, vía Visual Crossing.
# Cacheado 1 hora: mismo criterio que las simulaciones (un pronóstico no
# cambia de un minuto a otro, y no queremos gastar cuota de la API en
# cada rerun de Streamlit).
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _factor_clima_cached(local, visit):
    if not (CLIMA_MODULO_DISPONIBLE and WEATHER_API_KEY):
        return 1.0, None
    fecha_hora = HORARIOS_PARTIDO.get((local, visit))
    if not fecha_hora:
        return 1.0, None
    clima = obtener_clima_partido(local, fecha_hora, WEATHER_API_KEY)
    return _calc_factor_clima(clima), clima


# ─────────────────────────────────────────────────────────────────────────
# CUOTAS REALES (Value Betting) — The Odds API solo lista partidos
# próximos/en vivo, así que se trae UNA vez toda la jornada disponible y
# se indexa por (local, visita) en un dict — más barato que pedir cuota
# partido por partido, y respeta el quota de la API (1 crédito por
# consulta a /odds sin importar cuántos partidos traiga). Cacheado 1
# hora, mismo criterio que el clima: las cuotas se mueven, pero no tanto
# como para justificar refrescar en cada rerun de Streamlit.
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _cuotas_jornada_cached():
    if not (CUOTAS_MODULO_DISPONIBLE and ODDS_API_KEY):
        return {}
    partidos_con_cuota = obtener_cuotas_jornada(ODDS_API_KEY)
    return {(p["home_team"], p["away_team"]): p for p in partidos_con_cuota}


def _cuota_partido(local, visit):
    """Devuelve el dict de cuotas 1X2 para (local, visit) si The Odds
    API lo tiene listado, o None si no hay cuota disponible para ese
    partido (todavía muy lejano, ya jugado, o el partido no aparece en
    ninguna casa de la región consultada) — analizar_apuestas() ya
    maneja cuotas=None sin problema (retrocompatible)."""
    partido = _cuotas_jornada_cached().get((local, visit))
    return partido["cuotas"] if partido else None


def _cuotas_totales_partido(local, visit):
    """Devuelve la lista de líneas de Total de Goles reales para
    (local, visit) (ver liga_mx_cuotas._extraer_cuotas_totales()), o
    None si no hay cuota disponible — analizar_apuestas() ya maneja
    cuotas_totales=None sin problema (retrocompatible, se comporta
    igual que antes de agregar el check de apostabilidad real)."""
    partido = _cuotas_jornada_cached().get((local, visit))
    return partido["cuotas_totales"] if partido else None


def _partidos_de_hoy():
    tz_mx = timezone(timedelta(hours=-6))
    hoy = datetime.now(tz_mx).strftime("%Y-%m-%d")
    hoy_lista = []
    for p in PARTIDOS:
        local, visit, jornada, estadio, resultado, arbitro = p
        if resultado is not None:
            continue
        horario = HORARIOS_PARTIDO.get((local, visit))
        if horario and horario[:10] == hoy:
            hoy_lista.append(p)
    return hoy, hoy_lista


hoy, partidos_hoy_global = _partidos_de_hoy()

_mercados_susp = _mercados_suspendidos_cached()
if _mercados_susp:
    st.markdown(
        f'<div class="model-note" style="border-left-color:#c0685a">⏸️ <b>Retroalimentación automática:</b> '
        f'{", ".join(sorted(_mercados_susp))} — suspendido{"s" if len(_mercados_susp) > 1 else ""} temporalmente '
        f'de las apuestas sugeridas por bajo acierto real. Se reactiva{"n" if len(_mercados_susp) > 1 else ""} solo '
        f'en cuanto el acierto se recupere (ver detalle en 🎯 Historial de Apuestas → Auto-calibración).</div>',
        unsafe_allow_html=True,
    )

if partidos_hoy_global:
    with st.expander(f"🎰 APUESTAS MÁS FUERTES DE HOY ({hoy}) — Click para ver", expanded=True):
        st.caption("Se calcula automáticamente al abrir la página · solo señales de confianza ALTA")
        total_apuestas_hoy = 0
        patas_parlay_dia = []
        for local, visit, jornada, estadio, resultado, arbitro in partidos_hoy_global:
            horario = HORARIOS_PARTIDO.get((local, visit), "")
            hora_str = horario[11:] if horario else ""
            _fc, _ = _factor_clima_cached(local, visit)
            r_hoy = _simular_partido_cached(local, visit, N_SIMS_PARTIDO, PESO_ELO, PESO_ALTITUD, PESO_ARBITRO, _fc)
            sugs_hoy = analizar_apuestas(local, visit, r_hoy, mercados_suspendidos=_mercados_suspendidos_cached(),
                                          cuotas=_cuota_partido(local, visit),
                                          cuotas_totales=_cuotas_totales_partido(local, visit))
            _registrar_apuestas_sesion(local, visit, jornada, sugs_hoy, r=r_hoy, resultado_real=None)
            sugs_alta_hoy = [s for s in sugs_hoy if s["nivel"] == "ALTA"]
            if not sugs_alta_hoy:
                continue
            total_apuestas_hoy += len(sugs_alta_hoy)
            # La mejor pata de este partido (mayor confianza) entra al parlay del día
            mejor = sugs_alta_hoy[0]
            patas_parlay_dia.append({
                "local": local, "visitante": visit, "jornada": jornada,
                "mercado": mejor["mercado"], "seleccion": mejor["seleccion"].replace("✅ ", ""),
                "confianza": mejor["confianza"],
            })
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;margin:0.8rem 0 0.4rem;'
                f'padding-bottom:0.3rem;border-bottom:1px solid #1f4a2e">'
                f'<span style="font-size:0.82rem;color:#e8f0ea;font-weight:600">'
                f'{flag(local)} {local} vs {flag(visit)} {visit}</span>'
                f'<span style="font-size:0.68rem;color:#6b9b7d">⏰ {hora_str}h · Jornada {jornada}</span></div>',
                unsafe_allow_html=True,
            )
            for fila_inicio in range(0, len(sugs_alta_hoy), 3):
                fila = sugs_alta_hoy[fila_inicio:fila_inicio + 3]
                cols_hoy = st.columns(3)
                for i_ap, ap in enumerate(fila):
                    with cols_hoy[i_ap]:
                        st.markdown(
                            f'<div class="bet-card bet-card-alta"><div style="font-size:0.55rem;color:#6b9b7d;'
                            f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                            f'<div style="font-size:0.88rem;color:#e8f0ea;margin:0.2rem 0;font-weight:600">{ap["seleccion"]}</div>'
                            f'<div style="font-size:0.62rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div>'
                            f'{_badge_value_bet(ap)}{_badge_no_apostable(ap)}</div>',
                            unsafe_allow_html=True,
                        )
            parlay_hoy = armar_parlay(sugs_alta_hoy)
            if parlay_hoy:
                st.markdown(
                    f'<div class="parlay-card" style="padding:0.5rem 0.8rem"><span style="font-size:0.55rem;'
                    f'color:#e5007d;letter-spacing:2px">💛 PARLAY</span>'
                    f'<div style="font-size:0.76rem;color:#e5007d;margin:0.15rem 0">{parlay_hoy["texto"]}</div>'
                    f'<div style="font-size:0.6rem;color:#8fbfa0">Prob. combinada: '
                    f'<b style="color:#e5007d">{parlay_hoy["prob_combinada"]:.1f}%</b></div></div>',
                    unsafe_allow_html=True,
                )
        if total_apuestas_hoy == 0:
            st.info("Hoy no hay señales de confianza ALTA. El modelo es conservador.")
        st.caption("⚠️ Solo informativo · Apuesta responsablemente")

        # ── PARLAY DEL DÍA — combina la mejor pata de CADA partido de hoy ──
        if len(patas_parlay_dia) >= 2:
            st.markdown("---")
            prob_combinada_dia = 1.0
            for pata in patas_parlay_dia:
                prob_combinada_dia *= pata["confianza"] / 100
            prob_combinada_dia *= 100

            texto_patas = " + ".join(
                f'{flag(p["local"])}{p["local"]} vs {p["visitante"]}: {p["seleccion"]}'
                for p in patas_parlay_dia
            )
            st.markdown(
                f'<div class="parlay-card" style="border-color:#e5007d;padding:1rem">'
                f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.2rem;letter-spacing:2px;'
                f'color:#e5007d;margin-bottom:0.4rem">🎟️ PARLAY DEL DÍA — {len(patas_parlay_dia)} partidos</div>'
                f'<div style="font-size:0.78rem;color:#e8f0ea;line-height:1.6">{texto_patas}</div>'
                f'<div style="font-size:0.7rem;color:#8fbfa0;margin-top:0.5rem">Prob. combinada: '
                f'<b style="color:#e5007d">{prob_combinada_dia:.2f}%</b></div></div>',
                unsafe_allow_html=True,
            )
            if SUPABASE_DISPONIBLE:
                try:
                    guardar_parlay_diario(SUPABASE_URL, SUPABASE_KEY, hoy, patas_parlay_dia, prob_combinada_dia)
                except Exception:
                    pass


tab_pred, tab_res, tab_apuestas, tab_hist, tab_hist_ap, tab_parlays, tab_tabla, tab_info = st.tabs([
    "🎯 Predictor", "📊 Resultados reales", "🎰 Apuestas", "📈 Historial",
    "🎲 Apuestas Hist.", "🎟️ Parlays", "🏆 Tabla / Temporada", "⚙️ Modelo",
])

# ─────────────────────────────────────────────────────────────────────────
# TAB — Predictor
# ─────────────────────────────────────────────────────────────────────────
with tab_pred:
    col_izq, col_der = st.columns([1, 2.5], gap="large")
    with col_izq:
        st.markdown("#### Elige el partido")

        filtro_estado = st.radio(
            "Estado", ["⏳ Por jugarse", "✓ Jugados"],
            horizontal=True, key="filtro_estado_pred", label_visibility="collapsed",
        )
        es_por_jugarse = filtro_estado == "⏳ Por jugarse"
        partidos_filtrados = [p for p in PARTIDOS if (p[4] is None) == es_por_jugarse]

        if not partidos_filtrados:
            # fallback: si la categoría elegida está vacía (ej. "Jugados" al
            # arrancar la temporada), no se rompe nada — se usa la otra.
            st.caption(f"No hay partidos {filtro_estado.split(' ', 1)[1].lower()} todavía — mostrando la otra categoría.")
            partidos_filtrados = [p for p in PARTIDOS if (p[4] is None) != es_por_jugarse]

        jornadas = sorted(set(p[2] for p in partidos_filtrados))
        # "Por jugarse" arranca en la jornada más próxima (index 0, ya que
        # jornadas está ordenado ascendente). "Jugados" arranca en la más
        # reciente en vez de la Jornada 1 — es lo que casi siempre se quiere
        # revisar.
        idx_default = 0 if es_por_jugarse else len(jornadas) - 1
        jornada_sel = st.selectbox("Jornada", jornadas, index=idx_default, key=f"jornada_pred_{filtro_estado}")
        partidos_j = [p for p in partidos_filtrados if p[2] == jornada_sel]
        opciones = {f"{flag(p[0])} {p[0]} vs {flag(p[1])} {p[1]}": i for i, p in enumerate(partidos_j)}
        lbl_sel = st.selectbox("Partido", list(opciones.keys()), key=f"partido_pred_{filtro_estado}_{jornada_sel}")
        idx_sel = opciones[lbl_sel]
        local, visit, jornada, estadio, resultado_real, arbitro = partidos_j[idx_sel]

        st.markdown("---")
        st.caption(f"⚡ {N_SIMS_PARTIDO:,} simulaciones")
        btn = st.button("⚽ Simular partido", key="btn_simular")

        # ─────────────────────────────────────────────────────────────
        # SIMULAR JORNADA COMPLETA — detecta la jornada pendiente más
        # próxima (según fechas oficiales ya cargadas en PARTIDOS/
        # HORARIOS_PARTIDO) y simula sus partidos de un jalón, guardando
        # todo en el historial de Supabase con el mismo formato que ya
        # usa el flujo de "un partido a la vez".
        # ─────────────────────────────────────────────────────────────
        st.markdown("---")
        _jornada_detectada = detectar_jornada_actual()
        btn_jornada = False
        if _jornada_detectada is None:
            st.caption("No hay jornadas pendientes — temporada terminada.")
        else:
            st.caption(f"Jornada detectada: **Jornada {_jornada_detectada}** · 2,000,000 sims/partido")
            btn_jornada = st.button("⚽ Simular Jornada", key="btn_simular_jornada", type="primary")

    with col_der:
        alt = ALTITUD_EQUIPO.get(local)
        estado_tag = tag("tag-played", "✓ Jugado") if resultado_real else tag("tag-pending", "⏳ Por jugarse")
        alt_txt = f"⛰️ {alt:,} m &nbsp;·&nbsp; " if alt else ""
        st.markdown(
            f'{estado_tag}<div style="font-size:0.75rem;color:#6b9b7d;margin:0.5rem 0 1rem">'
            f'📍 {estadio or "Estadio TBD"} &nbsp;·&nbsp; {alt_txt}🧑‍⚖️ {arbitro or "Por confirmar"}</div>',
            unsafe_allow_html=True,
        )

        if resultado_real:
            gh, ga = resultado_real
            st.markdown(
                f'<div class="result-box" style="margin-bottom:1rem"><div class="team-name">'
                f'{flag(local)} {local} {gh} - {ga} {visit} {flag(visit)}</div>'
                f'<div class="prob-lbl">Resultado real</div></div>',
                unsafe_allow_html=True,
            )

        if btn or resultado_real:
            with st.spinner(f"Simulando {N_SIMS_PARTIDO:,} partidos..."):
                _fc, _clima_info = _factor_clima_cached(local, visit)
                r = simular_partido(local, visit, n=N_SIMS_PARTIDO,
                                     peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO,
                                     factor_clima=_fc, sesgo_por_equipo=_sesgo_equipo_cached())

            pa, pd_, pb = r["prob_home"], r["prob_draw"], r["prob_away"]
            st.markdown(
                f'<div style="font-size:0.6rem;color:#6b9b7d;letter-spacing:2px;text-transform:uppercase;'
                f'margin-bottom:0.2rem">Probabilidades — {r["n_sims"]:,} simulaciones</div>'
                f'<div class="prob-bar"><div class="bar-a" style="width:{pa:.1f}%"></div>'
                f'<div class="bar-draw" style="width:{pd_:.1f}%"></div>'
                f'<div class="bar-b" style="width:{pb:.1f}%"></div></div>',
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f'<div class="result-box"><div style="font-size:2.5rem">{flag(local)}</div>'
                            f'<div class="team-name">{local}</div><div class="prob-pct">{pa:.1f}%</div>'
                            f'<div class="prob-lbl">victoria</div><div class="goles-esp">{r["goles_home"]:.2f}</div>'
                            f'<div class="prob-lbl">goles esp.</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="result-box result-box-draw"><div style="font-size:2.5rem">🤝</div>'
                            f'<div class="team-name" style="color:#9ca3af">Empate</div>'
                            f'<div class="prob-pct prob-pct-draw">{pd_:.1f}%</div>'
                            f'<div class="prob-lbl">probabilidad</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="result-box result-box-b"><div style="font-size:2.5rem">{flag(visit)}</div>'
                            f'<div class="team-name">{visit}</div><div class="prob-pct prob-pct-b">{pb:.1f}%</div>'
                            f'<div class="prob-lbl">victoria</div><div class="goles-esp">{r["goles_away"]:.2f}</div>'
                            f'<div class="prob-lbl">goles esp.</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            cm1, cm2 = st.columns(2)
            with cm1:
                st.markdown('<div style="font-size:0.6rem;color:#6b9b7d;letter-spacing:2px;'
                            'text-transform:uppercase;margin-bottom:0.5rem">Top 5 marcadores</div>', unsafe_allow_html=True)
                badges = ""
                for i, (marcador, cnt) in enumerate(r["top5"]):
                    pct = cnt / r["n_sims"] * 100
                    cls = "score-badge score-badge-top" if i == 0 else "score-badge"
                    badges += f'<div class="{cls}">{marcador[0]}–{marcador[1]}<div style="font-size:0.55rem;color:#6b9b7d">{pct:.1f}%</div></div>'
                st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:0.2rem">{badges}</div>', unsafe_allow_html=True)
            with cm2:
                st.markdown('<div style="font-size:0.6rem;color:#6b9b7d;letter-spacing:2px;'
                            'text-transform:uppercase;margin-bottom:0.5rem">Tarjetas / Córners esperados</div>', unsafe_allow_html=True)
                tc1, tc2 = st.columns(2)
                with tc1:
                    st.markdown(f'<div class="metric-box"><div class="metric-val">{r["amarillas_esp"]}</div>'
                                f'<div class="metric-lbl">Amarillas</div></div>', unsafe_allow_html=True)
                with tc2:
                    st.markdown(f'<div class="metric-box"><div class="metric-val">{r["corners_esp"]:.1f}</div>'
                                f'<div class="metric-lbl">Córners</div></div>', unsafe_allow_html=True)

            st.markdown(
                f'<div class="model-note">λ_local={r["lam_home"]} · λ_visita={r["lam_away"]} · '
                f'Árbitro: {r["arbitro"]} · Tarjetas totales esp. (roja=2pts): {r["tarjetas_totales_esp"]}</div>',
                unsafe_allow_html=True,
            )
            if _clima_info:
                st.markdown(
                    f'<div class="model-note">🌤️ Clima en {local}: {_clima_info.get("temp_c")}°C · '
                    f'humedad {_clima_info.get("humedad_pct")}% · prob. lluvia {_clima_info.get("prob_lluvia_pct")}% · '
                    f'{_clima_info.get("condiciones", "")} · factor aplicado a λ: ×{_fc:.3f}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)
            sugs = analizar_apuestas(local, visit, r, mercados_suspendidos=_mercados_suspendidos_cached(),
                                      cuotas=_cuota_partido(local, visit),
                                      cuotas_totales=_cuotas_totales_partido(local, visit))
            _registrar_apuestas_sesion(local, visit, jornada, sugs, r=r, resultado_real=resultado_real)
            if sugs:
                st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;'
                            'letter-spacing:2px;color:#e5007d;margin-bottom:0.75rem">🎰 APUESTAS SUGERIDAS</div>',
                            unsafe_allow_html=True)
                # Todas las que cumplan el umbral (dinámico) — en filas de hasta 3 columnas
                for fila_inicio in range(0, len(sugs), 3):
                    fila = sugs[fila_inicio:fila_inicio + 3]
                    cols_ap = st.columns(3)
                    for i_ap, ap in enumerate(fila):
                        with cols_ap[i_ap]:
                            st.markdown(
                                f'<div class="bet-card bet-card-alta"><div style="font-size:0.6rem;color:#6b9b7d;'
                                f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                                f'<div style="font-size:0.95rem;color:#e8f0ea;margin:0.3rem 0;font-weight:600">{ap["seleccion"]}</div>'
                                f'<div style="font-size:0.65rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div>'
                                f'<div style="font-size:0.6rem;color:#6b9b7d;margin-top:0.3rem">{ap["nota"]}</div>'
                                f'{_badge_value_bet(ap)}{_badge_no_apostable(ap)}</div>',
                                unsafe_allow_html=True,
                            )
                parlay = armar_parlay(sugs)
                if parlay:
                    st.markdown(
                        f'<div class="parlay-card"><span style="font-size:0.6rem;color:#e5007d;letter-spacing:2px">'
                        f'💛 PARLAY SUGERIDO</span><div style="font-size:0.85rem;color:#e5007d;margin:0.2rem 0">{parlay["texto"]}</div>'
                        f'<div style="font-size:0.65rem;color:#8fbfa0">Prob. combinada: '
                        f'<b style="color:#e5007d">{parlay["prob_combinada"]:.1f}%</b></div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("Sin señales claras de apuesta para este partido — modelo conservador.")

    # ─────────────────────────────────────────────────────────────────
    # Resultado de "Simular Jornada" — a todo el ancho del tab, debajo
    # de las columnas del partido individual (el botón vive en col_izq,
    # pero el resultado no cabe bien en 1/3.5 del ancho de pantalla).
    # ─────────────────────────────────────────────────────────────────
    if btn_jornada:
        with st.spinner(f"Simulando Jornada {_jornada_detectada} completa..."):
            sesgo_actual = _sesgo_equipo_cached()
            resultado_jornada = simular_jornada_completa(
                jornada=_jornada_detectada, n=2_000_000,
                peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO,
                mercados_suspendidos=_mercados_suspendidos_cached(),
                sesgo_por_equipo=sesgo_actual,
                cuotas_por_partido=_cuotas_jornada_cached(),
            )
            resumen_guardado = {"partidos_guardados": 0, "apuestas_guardadas": 0, "errores": []}
            if SUPABASE_DISPONIBLE:
                resumen_guardado = guardar_jornada_completa(SUPABASE_URL, SUPABASE_KEY, resultado_jornada)
        st.session_state["resultado_jornada_simulada"] = resultado_jornada
        st.session_state["resumen_guardado_jornada"] = resumen_guardado

    if "resultado_jornada_simulada" in st.session_state:
        st.markdown("---")
        resultado_jornada = st.session_state["resultado_jornada_simulada"]
        resumen_guardado = st.session_state.get("resumen_guardado_jornada", {})

        st.markdown(f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;'
                    f'letter-spacing:2px;color:#e5007d;margin-bottom:0.5rem">⚽ JORNADA {resultado_jornada["jornada"]} SIMULADA</div>',
                    unsafe_allow_html=True)

        if SUPABASE_DISPONIBLE:
            if resumen_guardado.get("errores"):
                st.warning(f"⚠️ Guardado parcial: {resumen_guardado['partidos_guardados']} partidos guardados, "
                           f"{len(resumen_guardado['errores'])} con error.")
            else:
                st.success(f"✅ {resumen_guardado.get('partidos_guardados', 0)} partidos guardados en el "
                           f"historial · {resumen_guardado.get('apuestas_guardadas', 0)} apuestas registradas.")
        else:
            st.info("Supabase no está conectado — la simulación se muestra abajo pero no se guarda en el historial.")

        for p in resultado_jornada["partidos"]:
            r_p = p["resultado_sim"]
            pa_p, pd_p, pb_p = r_p["prob_home"], r_p["prob_draw"], r_p["prob_away"]
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;margin:1rem 0 0.3rem;'
                f'padding-bottom:0.3rem;border-bottom:1px solid #1f4a2e">'
                f'<span style="font-size:0.85rem;color:#e8f0ea;font-weight:600">'
                f'{flag(p["local"])} {p["local"]} vs {flag(p["visitante"])} {p["visitante"]}</span>'
                f'<span style="font-size:0.68rem;color:#6b9b7d">🧑‍⚖️ {p["arbitro"]}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="prob-bar"><div class="bar-a" style="width:{pa_p:.1f}%"></div>'
                f'<div class="bar-draw" style="width:{pd_p:.1f}%"></div>'
                f'<div class="bar-b" style="width:{pb_p:.1f}%"></div></div>'
                f'<div style="font-size:0.68rem;color:#8fbfa0;margin-bottom:0.4rem">'
                f'{p["local"]} {pa_p:.1f}% · Empate {pd_p:.1f}% · {p["visitante"]} {pb_p:.1f}%</div>',
                unsafe_allow_html=True,
            )
            if p["apuestas"]:
                for fila_inicio in range(0, len(p["apuestas"]), 3):
                    fila = p["apuestas"][fila_inicio:fila_inicio + 3]
                    cols_j = st.columns(3)
                    for i_ap, ap in enumerate(fila):
                        with cols_j[i_ap]:
                            st.markdown(
                                f'<div class="bet-card bet-card-alta"><div style="font-size:0.55rem;color:#6b9b7d;'
                                f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                                f'<div style="font-size:0.85rem;color:#e8f0ea;margin:0.2rem 0;font-weight:600">{ap["seleccion"]}</div>'
                                f'<div style="font-size:0.6rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div>'
                                f'{_badge_value_bet(ap)}{_badge_no_apostable(ap)}</div>',
                                unsafe_allow_html=True,
                            )
            else:
                st.caption("Sin señales de confianza para este partido.")
            if p["parlay"]:
                st.markdown(
                    f'<div class="parlay-card" style="padding:0.5rem 0.8rem"><span style="font-size:0.55rem;'
                    f'color:#e5007d;letter-spacing:2px">💛 PARLAY</span>'
                    f'<div style="font-size:0.76rem;color:#e5007d;margin:0.15rem 0">{p["parlay"]["texto"]}</div>'
                    f'<div style="font-size:0.6rem;color:#8fbfa0">Prob. combinada: '
                    f'<b style="color:#e5007d">{p["parlay"]["prob_combinada"]:.1f}%</b></div></div>',
                    unsafe_allow_html=True,
                )

        # ── SUPER PARLAY DE LA JORNADA — estilo PlayDoit: combina TODOS
        # los partidos de la jornada en un solo boleto, permitiendo que
        # un mismo partido aporte 2+ patas (ver armar_super_parlay_
        # jornada() en liga_mx_algoritmo.py). ────────────────────────
        super_parlay = armar_super_parlay_jornada(resultado_jornada["partidos"])
        if super_parlay:
            st.markdown("---")
            patas_html = "".join(
                f'<div style="font-size:0.72rem;color:#e8f0ea;margin-top:0.3rem;padding-top:0.3rem;'
                f'border-top:1px solid rgba(240,192,64,0.15)">'
                f'{flag(pata["local"])} {pata["local"]} vs {flag(pata["visitante"])} {pata["visitante"]} — '
                f'<span style="color:#f0c040">{pata["mercado"]}</span> → {pata["seleccion"].replace("✅ ", "")} '
                f'<span style="color:#4ade80">({pata["confianza"]:.0f}%)</span></div>'
                for pata in super_parlay["patas"]
            )
            st.markdown(
                f'<div class="parlay-card" style="border-color:#e5007d;padding:1.1rem">'
                f'<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;letter-spacing:2px;'
                f'color:#e5007d;margin-bottom:0.3rem">🎟️ SUPER PARLAY — JORNADA {resultado_jornada["jornada"]}</div>'
                f'<div style="font-size:0.68rem;color:#8fbfa0;margin-bottom:0.4rem">'
                f'{super_parlay["n_partidos"]} partidos · {len(super_parlay["patas"])} entradas combinadas</div>'
                f'{patas_html}'
                f'<div style="font-size:0.75rem;color:#8fbfa0;margin-top:0.6rem;padding-top:0.5rem;'
                f'border-top:1px solid rgba(240,192,64,0.25)">Prob. combinada: '
                f'<b style="color:#e5007d;font-size:0.95rem">{super_parlay["prob_combinada"]:.2f}%</b></div></div>',
                unsafe_allow_html=True,
            )
            st.caption("⚠️ Un boleto con muchas entradas es mucho más difícil de acertar completo — la probabilidad combinada baja rápido entre más entradas se agregan. Solo informativo.")

# ─────────────────────────────────────────────────────────────────────────
# TAB — Resultados reales
# ─────────────────────────────────────────────────────────────────────────
with tab_res:
    st.markdown("#### Resultados registrados")
    st.caption("Partidos ya disputados del Apertura 2026.")
    jugados = [p for p in PARTIDOS if p[4] is not None]
    if not jugados:
        st.info("Aún no hay resultados registrados.")
    else:
        for jn in sorted(set(p[2] for p in jugados)):
            st.markdown(f"**Jornada {jn}**")
            for local, visit, jornada, estadio, res, arb in jugados:
                if jornada != jn:
                    continue
                gh, ga = res
                color = "#0d1f16" if gh != ga else "#0d1827"
                ganador = (f"→ Ganó **{local}**" if gh > ga else f"→ Ganó **{visit}**" if ga > gh else "→ **Empate**")
                st.markdown(
                    f'<div style="background:{color};border-radius:8px;padding:0.5rem 1rem;margin-bottom:0.35rem;font-size:0.88rem">'
                    f'{flag(local)} {local} <b style="font-size:1.1rem;color:#4ade80;margin:0 0.4rem">{gh}–{ga}</b>'
                    f'{visit} {flag(visit)}<span style="color:#6b9b7d;font-size:0.72rem;margin-left:0.8rem">'
                    f'📍 {estadio} · {ganador}</span></div>', unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────
# TAB — Apuestas (del día)
# ─────────────────────────────────────────────────────────────────────────
with tab_apuestas:
    st.markdown("### 🎰 Apuestas más fuertes de hoy")
    st.caption("Mismo cálculo que el panel de arriba de la página — aquí puedes verlo con más detalle.")

    if not partidos_hoy_global:
        st.info(f"No hay partidos programados para hoy ({hoy}). Explora otras jornadas en el tab Predictor.")
    else:
        for local, visit, jornada, estadio, resultado, arbitro in partidos_hoy_global:
            horario = HORARIOS_PARTIDO.get((local, visit), "")
            hora_str = horario[11:] if horario else ""
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;margin:1rem 0 0.5rem;'
                f'padding-bottom:0.4rem;border-bottom:1px solid #1f4a2e">'
                f'<span style="font-size:0.85rem;color:#e8f0ea;font-weight:600">'
                f'{flag(local)} {local} vs {flag(visit)} {visit}</span>'
                f'<span style="font-size:0.7rem;color:#6b9b7d">⏰ {hora_str}h · Jornada {jornada}</span></div>',
                unsafe_allow_html=True,
            )
            _fc_dia, _ = _factor_clima_cached(local, visit)
            r = _simular_partido_cached(local, visit, N_SIMS_PARTIDO, PESO_ELO, PESO_ALTITUD, PESO_ARBITRO, _fc_dia)
            sugs = analizar_apuestas(local, visit, r, mercados_suspendidos=_mercados_suspendidos_cached(),
                                      cuotas=_cuota_partido(local, visit),
                                      cuotas_totales=_cuotas_totales_partido(local, visit))  # ya vienen solo las que cumplen el umbral dinámico
            _registrar_apuestas_sesion(local, visit, jornada, sugs, r=r, resultado_real=resultado)
            if not sugs:
                st.caption("Sin señales de confianza ALTA para este partido.")
            else:
                # Todas las que cumplan el umbral dinámico — en filas de hasta 3 columnas
                for fila_inicio in range(0, len(sugs), 3):
                    fila = sugs[fila_inicio:fila_inicio + 3]
                    cols_ap = st.columns(3)
                    for i_ap, ap in enumerate(fila):
                        with cols_ap[i_ap]:
                            st.markdown(
                                f'<div class="bet-card bet-card-alta"><div style="font-size:0.55rem;color:#6b9b7d;'
                                f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                                f'<div style="font-size:0.9rem;color:#e8f0ea;margin:0.2rem 0;font-weight:600">{ap["seleccion"]}</div>'
                                f'<div style="font-size:0.65rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div>'
                                f'{_badge_value_bet(ap)}{_badge_no_apostable(ap)}</div>',
                                unsafe_allow_html=True,
                            )
                parlay = armar_parlay(sugs)
                if parlay:
                    st.markdown(
                        f'<div class="parlay-card" style="padding:0.6rem 0.9rem"><span style="font-size:0.55rem;'
                        f'color:#e5007d;letter-spacing:2px">💛 PARLAY</span>'
                        f'<div style="font-size:0.78rem;color:#e5007d;margin:0.15rem 0">{parlay["texto"]}</div>'
                        f'<div style="font-size:0.6rem;color:#8fbfa0">Prob. combinada: '
                        f'<b style="color:#e5007d">{parlay["prob_combinada"]:.1f}%</b></div></div>',
                        unsafe_allow_html=True,
                    )
    st.markdown('<div style="font-size:0.65rem;color:#4a5568;padding-top:1rem;border-top:1px solid #1f4a2e;'
                'margin-top:1rem">⚠️ Solo informativo · Apuesta responsablemente</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────
# TAB — Historial (predicciones vs resultados reales)
# ─────────────────────────────────────────────────────────────────────────
with tab_hist:
    st.markdown("#### 📈 Historial de predicciones vs resultados reales")
    jugados = [p for p in PARTIDOS if p[4] is not None]
    if not jugados:
        st.info("Aún no hay partidos terminados para calcular accuracy. Se irá llenando conforme avance el torneo.")
    else:
        aciertos_ganador, aciertos_over25, total = 0, 0, 0
        filas = []
        for local, visit, jornada, estadio, res, arb in jugados:
            try:
                r = simular_partido(local, visit, n=50_000, peso_elo=PESO_ELO,
                                     peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO)
                favorito = local if r["prob_home"] > r["prob_away"] else visit
                gh, ga = res
                ganador_real = local if gh > ga else (visit if ga > gh else "Empate")
                correcto = favorito == ganador_real
                if correcto:
                    aciertos_ganador += 1
                if ((gh + ga) > 2) == (r["prob_over25"] > 50):
                    aciertos_over25 += 1
                total += 1
                filas.append({"partido": f"{flag(local)} {local} vs {flag(visit)} {visit}",
                               "resultado": f"{gh}-{ga}", "favorito": favorito, "real": ganador_real, "ok": correcto})
            except Exception:
                continue
        if total > 0:
            c1, c2, c3 = st.columns(3)
            acc_g = aciertos_ganador / total * 100
            acc_o = aciertos_over25 / total * 100
            with c1:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{acc_g:.1f}%</div>'
                            f'<div class="metric-lbl">Accuracy ganador</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{acc_o:.1f}%</div>'
                            f'<div class="metric-lbl">Accuracy Over/Under 2.5</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{total}</div>'
                            f'<div class="metric-lbl">Partidos analizados</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            for f in filas:
                icono = "✅" if f["ok"] else "❌"
                color = "#0d2818" if f["ok"] else "#1a0d0d"
                st.markdown(
                    f'<div style="background:{color};border-radius:8px;padding:0.5rem 0.9rem;margin-bottom:0.3rem;'
                    f'font-size:0.82rem">{icono} {f["partido"]} — {f["resultado"]} · Modelo: '
                    f'<b style="color:#e5007d">{f["favorito"]}</b> · Real: {f["real"]}</div>', unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────
# TAB — Apuestas Hist.
# ─────────────────────────────────────────────────────────────────────────
with tab_hist_ap:
    st.markdown("#### 🎲 Historial de apuestas sugeridas")

    if not SUPABASE_DISPONIBLE:
        st.warning(
            "⚠️ Supabase no está conectado — mostrando solo el historial de **esta sesión** "
            "(se borra al recargar la página). Agrega `SUPABASE_URL_LIGAMX` y `SUPABASE_KEY_LIGAMX` "
            "a los Secrets de Streamlit Cloud para que esto persista de verdad."
        )
        hist = st.session_state["historial_apuestas_sesion"]
        if not hist:
            st.info("Todavía no has simulado ningún partido en esta sesión. Ve al tab Predictor o Apuestas.")
        else:
            for h in reversed(hist):
                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1f4a2e;border-radius:8px;padding:0.5rem 0.9rem;'
                    f'margin-bottom:0.3rem"><span style="color:#e8f0ea;font-size:0.8rem;font-weight:600">'
                    f'{flag(h["local"])} {h["local"]} vs {flag(h["visit"])} {h["visit"]}</span>'
                    f'<span style="color:#6b9b7d;font-size:0.7rem;margin-left:0.8rem">Jornada {h["jornada"]} · {h["hora_registro"]}</span>'
                    f'<div style="font-size:0.75rem;color:#f0c040;margin-top:0.2rem">📋 {h["mercado"]} → {h["seleccion"]} '
                    f'<span style="color:#4ade80">({h["confianza"]:.0f}%)</span></div></div>',
                    unsafe_allow_html=True,
                )
    else:
        historial = cargar_historial_apuestas(SUPABASE_URL, SUPABASE_KEY)
        historial = [h for h in historial if not str(h.get("local", "")).startswith("TBD")]

        if not historial:
            st.info("⏳ Aún no hay apuestas registradas. Se guardan automáticamente cada vez que simulas un partido.")
        else:
            stats = calcular_stats_apuestas(historial)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["accuracy"]:.1f}%</div>'
                            f'<div class="metric-lbl">Accuracy apuestas</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-box"><div class="metric-val" style="color:#4ade80">{stats["aciertos"]}</div>'
                            f'<div class="metric-lbl">✅ Aciertos</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-box"><div class="metric-val" style="color:#f87171">{stats["fallos"]}</div>'
                            f'<div class="metric-lbl">❌ Fallos</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["total_pendientes"]}</div>'
                            f'<div class="metric-lbl">⏳ Pendientes</div></div>', unsafe_allow_html=True)

            # ── Panel de auto-calibración: ¿el 80% que dice el modelo es
            # realmente 80% de acierto? Desglosado por mercado. ──────────
            stats_mercado = calcular_stats_por_mercado(historial)
            if stats_mercado:
                with st.expander("🎯 Auto-calibración por mercado — ¿el modelo cumple lo que promete?", expanded=False):
                    st.caption(
                        "Compara la confianza promedio que dijo el modelo al sugerir cada mercado contra "
                        "el acierto real una vez que el partido ya se jugó. Solo se muestran mercados con "
                        "3+ apuestas ya evaluadas — con menos, la tasa de acierto es puro ruido."
                    )
                    for fm in stats_mercado:
                        color = ("#c0685a" if fm["brecha"] > 5 else
                                 "#4ade80" if fm["brecha"] < -5 else "#e8f0ea")
                        texto_pendientes = f" · {fm['n_pendientes']} pendientes" if fm["n_pendientes"] else ""
                        st.markdown(
                            f'<div style="background:#111827;border:1px solid #1f4a2e;border-radius:8px;'
                            f'padding:0.6rem 1rem;margin-bottom:0.4rem">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center">'
                            f'<span style="color:#e8f0ea;font-size:0.85rem;font-weight:600">{fm["mercado"]}</span>'
                            f'<span style="font-size:0.7rem;color:#6b9b7d">{fm["n_evaluadas"]} evaluadas{texto_pendientes}</span></div>'
                            f'<div style="font-size:0.78rem;margin-top:0.3rem;color:#8fbfa0">'
                            f'Modelo dijo: <b>{fm["confianza_promedio"]:.1f}%</b> &nbsp;·&nbsp; '
                            f'Acertó de verdad: <b style="color:{color}">{fm["accuracy_real"]:.1f}%</b> '
                            f'({fm["aciertos"]}/{fm["n_evaluadas"]})</div>'
                            f'<div style="font-size:0.72rem;color:{color};margin-top:0.15rem">{fm["diagnostico"]}'
                            f' (brecha: {fm["brecha"]:+.1f} pts)</div></div>',
                            unsafe_allow_html=True,
                        )

            # ── Panel de Brier Score / Calibración global (1X2) ──────────
            historial_predicciones = cargar_historial_predicciones(SUPABASE_URL, SUPABASE_KEY)
            brier_data = calcular_brier_score(historial_predicciones)
            if brier_data["n_evaluadas"] > 0:
                with st.expander("📐 Calibración del modelo (Brier Score) — ¿qué tan confiables son los %?", expanded=False):
                    st.caption(
                        "Brier Score mide qué tan bien calibradas están las probabilidades del modelo, no "
                        "solo si acertó el ganador. 0 = predicciones perfectas · 0.667 = igual que tirar una "
                        "moneda entre 3 opciones · valores claramente por debajo de 0.667 indican que el "
                        "modelo aporta información real."
                    )
                    color_brier = "#4ade80" if brier_data["brier"] < 0.55 else ("#f0c040" if brier_data["brier"] < 0.667 else "#f87171")
                    st.markdown(
                        f'<div class="metric-box" style="max-width:220px"><div class="metric-val" style="color:{color_brier}">'
                        f'{brier_data["brier"]}</div><div class="metric-lbl">Brier Score global · {brier_data["n_evaluadas"]} evaluadas</div></div>',
                        unsafe_allow_html=True,
                    )
                    if brier_data["por_equipo"]:
                        st.markdown("###### Peor calibrados (más partidos primero para que el número sea confiable)")
                        df_brier = pd.DataFrame(brier_data["por_equipo"])
                        df_brier.insert(0, "", df_brier["equipo"].map(flag))
                        df_brier.columns = ["", "Equipo", "Brier promedio", "Partidos evaluados"]
                        st.dataframe(df_brier, use_container_width=True, hide_index=True)

                    calibracion = calcular_calibracion_por_bin(historial_predicciones)
                    if calibracion:
                        st.markdown("###### Calibración por rango de confianza")
                        st.caption("Brecha negativa = el modelo es prudente (dice menos de lo que en realidad acierta). Brecha positiva = el modelo es sobreconfiado (promete más de lo que cumple).")
                        df_calib = pd.DataFrame(calibracion)
                        df_calib.columns = ["Rango prometido", "Prometido promedio (%)", "Real (%)", "Brecha", "N observaciones"]
                        st.dataframe(df_calib, use_container_width=True, hide_index=True)

            if stats["evaluadas"]:
                st.markdown("##### ✅ Apuestas evaluadas")
                for ap in stats["evaluadas"]:
                    icono = "✅" if ap["acierto"] else "❌"
                    color = "#0d2818" if ap["acierto"] else "#1a0d0d"
                    st.markdown(
                        f'<div style="background:{color};border-radius:8px;padding:0.5rem 0.9rem;margin-bottom:0.3rem;'
                        f'font-size:0.8rem">{icono} {flag(ap["local"])} {ap["local"]} vs {flag(ap["visitante"])} {ap["visitante"]} '
                        f'<span style="color:#6b9b7d;font-size:0.7rem;margin-left:0.5rem">J{ap["jornada"]} · {ap.get("resultado_real","")}</span>'
                        f'<div style="font-size:0.72rem;color:#f0c040;margin-top:0.2rem">📋 {ap["mercado"]} → {ap["seleccion"]} '
                        f'<span style="color:#4ade80">({ap["confianza"]:.0f}%)</span></div></div>',
                        unsafe_allow_html=True,
                    )

            if stats["pendientes"]:
                st.markdown("---")
                st.markdown(f"##### ⏳ Apuestas pendientes ({len(stats['pendientes'])})")
                for ap in stats["pendientes"]:
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid #1f4a2e;border-radius:8px;padding:0.5rem 0.9rem;'
                        f'margin-bottom:0.3rem;font-size:0.8rem">{flag(ap["local"])} {ap["local"]} vs {flag(ap["visitante"])} {ap["visitante"]} '
                        f'<span style="color:#6b9b7d;font-size:0.7rem;margin-left:0.5rem">J{ap["jornada"]}</span>'
                        f'<div style="font-size:0.72rem;color:#f0c040;margin-top:0.2rem">📋 {ap["mercado"]} → {ap["seleccion"]} '
                        f'<span style="color:#4ade80">({ap["confianza"]:.0f}%)</span></div></div>',
                        unsafe_allow_html=True,
                    )
        st.markdown(
            '<div class="model-note">🎯 Solo apuestas de confianza ALTA. Tarjetas y córners quedan '
            '"pendientes" hasta que agregues manualmente el resultado real de amarillas/córners '
            '(igual que hacías con DATOS_REALES en el Mundial) — 1X2, doble oportunidad y goles se '
            'evalúan automáticamente en cuanto el partido tiene resultado.</div>',
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────────────────
# TAB — Parlays (historial del "parlay del día" — todas las mejores
# apuestas de cada partido del día, combinadas en una sola)
# ─────────────────────────────────────────────────────────────────────────
with tab_parlays:
    st.markdown("#### 🎟️ Historial de Parlays del Día")
    st.caption(
        "Cada día se arma UN parlay combinando la mejor apuesta (mayor confianza) de "
        "cada partido de esa fecha — igual que ves en el panel de arriba de la página. "
        "Para que el parlay completo 'gane', TODAS sus entradas tienen que acertar."
    )

    if not SUPABASE_DISPONIBLE:
        st.warning(
            "⚠️ Supabase no está conectado — los parlays del día no se pueden guardar ni "
            "consultar en este modo. Conecta `SUPABASE_URL_LIGAMX` y `SUPABASE_KEY_LIGAMX` "
            "en los Secrets de Streamlit Cloud."
        )
    else:
        historial_parlays = cargar_historial_parlays(SUPABASE_URL, SUPABASE_KEY)
        if not historial_parlays:
            st.info("⏳ Aún no hay parlays guardados. Se arma uno automáticamente cada día que haya "
                    "al menos 2 partidos con apuestas de confianza ALTA.")
        else:
            ganados = [p for p in historial_parlays if p.get("resultado") == "ganado"]
            perdidos = [p for p in historial_parlays if p.get("resultado") == "perdido"]
            pendientes_p = [p for p in historial_parlays if p.get("resultado") == "pendiente"]
            evaluados = len(ganados) + len(perdidos)
            accuracy_parlay = (len(ganados) / evaluados * 100) if evaluados else 0.0

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{accuracy_parlay:.1f}%</div>'
                            f'<div class="metric-lbl">Accuracy parlays</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-box"><div class="metric-val" style="color:#4ade80">{len(ganados)}</div>'
                            f'<div class="metric-lbl">✅ Ganados</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-box"><div class="metric-val" style="color:#f87171">{len(perdidos)}</div>'
                            f'<div class="metric-lbl">❌ Perdidos</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="metric-box"><div class="metric-val">{len(pendientes_p)}</div>'
                            f'<div class="metric-lbl">⏳ Pendientes</div></div>', unsafe_allow_html=True)

            st.markdown("---")
            for parlay in historial_parlays:
                resultado_p = parlay.get("resultado", "pendiente")
                icono = {"ganado": "✅", "perdido": "❌", "pendiente": "⏳"}.get(resultado_p, "⏳")
                color = {"ganado": "#0d2818", "perdido": "#1a0d0d", "pendiente": "#111827"}.get(resultado_p, "#111827")
                borde = {"ganado": "#2d6b45", "perdido": "#6b2d2d", "pendiente": "#1f4a2e"}.get(resultado_p, "#1f4a2e")

                selecciones_p = parlay.get("selecciones", [])
                if isinstance(selecciones_p, str):
                    import json as _json
                    try:
                        selecciones_p = _json.loads(selecciones_p)
                    except Exception:
                        selecciones_p = []

                patas_html = "".join(
                    f'<div style="font-size:0.72rem;color:#e8f0ea;margin-top:0.15rem">'
                    f'{flag(s.get("local",""))} {s.get("local","")} vs {s.get("visitante","")} — '
                    f'<span style="color:#f0c040">{s.get("mercado","")}</span> → {s.get("seleccion","")} '
                    f'<span style="color:#4ade80">({s.get("confianza",0):.0f}%)</span></div>'
                    for s in selecciones_p
                )
                st.markdown(
                    f'<div style="background:{color};border:1px solid {borde};border-radius:10px;'
                    f'padding:0.8rem 1rem;margin-bottom:0.6rem">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<span style="font-size:0.85rem;color:#e8f0ea;font-weight:600">{icono} {parlay.get("fecha","")} '
                    f'— {parlay.get("n_partidos", len(selecciones_p))} partidos</span>'
                    f'<span style="font-size:0.7rem;color:#e5007d">Prob. combinada: {parlay.get("prob_combinada",0):.1f}%</span>'
                    f'</div>{patas_html}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown(
            '<div class="model-note">🎟️ Un parlay del día "pierde" si al menos una entrada falla, y '
            '"gana" solo si TODAS las patas aciertan. Las patas de Tarjetas/Córners quedan '
            '"pendientes" hasta que agregues el dato real a DATOS_REALES_LIGAMX.</div>',
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────────────────
# TAB — Tabla / Temporada (posiciones actuales + simular todo el torneo)
# ─────────────────────────────────────────────────────────────────────────
with tab_tabla:
    st.markdown("### 📊 Tabla actual — solo partidos ya jugados")
    st.caption("Debe coincidir exactamente con la tabla oficial de Liga MX/ESPN en todo momento.")

    tabla_real, n_jugados = tabla_actual_real()
    if n_jugados == 0:
        st.info("Todavía no hay partidos jugados registrados.")
    else:
        df_real = pd.DataFrame(tabla_real)
        df_real = df_real[["posicion", "equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "PTS"]]
        df_real.insert(1, "", df_real["equipo"].map(flag))
        df_real.columns = ["#", "", "Club", "PJ", "G", "E", "P", "GF", "GC", "DG", "Pts"]
        st.dataframe(
            df_real, use_container_width=True, hide_index=True,
            column_config={"#": st.column_config.NumberColumn(width="small")},
        )
        st.caption(f"📅 {n_jugados} partido(s) jugado(s) hasta ahora · empatados comparten posición, igual que la tabla oficial")

    st.markdown("---")
    st.markdown("### 🔮 Proyección de fin de temporada (simulada)")
    st.caption(
        "Esto SÍ mezcla los resultados reales de arriba con una simulación del resto de la "
        "temporada — te da una idea de cómo podría terminar, pero no es la tabla oficial de hoy."
    )

    if st.button("🔄 Recalcular proyección y Liguilla", key="btn_recalcular_tabla") or "resultado_temporada" not in st.session_state:
        with st.spinner("Simulando la temporada completa..."):
            st.session_state["resultado_temporada"] = simular_temporada(
                peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO)

    resultado_temp = st.session_state["resultado_temporada"]
    df_tabla = pd.DataFrame(resultado_temp["tabla_final"])
    df_tabla = df_tabla[["posicion", "equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "PTS"]]
    df_tabla.insert(1, "", df_tabla["equipo"].map(flag))
    df_tabla.columns = ["#", "", "Equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "Pts"]
    st.dataframe(
        df_tabla, use_container_width=True, hide_index=True,
        column_config={"#": st.column_config.NumberColumn(width="small")},
    )
    st.caption("🟢 Los primeros 8 lugares clasifican a la Liguilla (en la proyección)")

    st.markdown("### 🏆 Liguilla simulada (con la tabla de arriba)")
    liguilla = resultado_temp["liguilla"]
    col_cf, col_sf, col_f = st.columns(3)
    with col_cf:
        st.markdown("**Cuartos de Final**")
        for serie in liguilla["cuartos"]:
            st.markdown(f"- {serie['marcador_global']} → **{flag(serie['ganador'])} {serie['ganador']}**")
    with col_sf:
        st.markdown("**Semifinales**")
        for serie in liguilla["semis"]:
            st.markdown(f"- {serie['marcador_global']} → **{flag(serie['ganador'])} {serie['ganador']}**")
    with col_f:
        st.markdown("**Final**")
        st.markdown(f"- {liguilla['final']['marcador_global']}")
        st.success(f"🏆 Campeón: {flag(liguilla['campeon'])} {liguilla['campeon']}")

    st.markdown("---")
    st.markdown("### 🎲 Simular todo el torneo (Montecarlo)")
    st.caption(
        "Corre la temporada completa (17 jornadas + Liguilla) muchas veces y agrega "
        "probabilidades reales de clasificar y ser campeón — el equivalente de liga regular "
        "a las 10M simulaciones por partido."
    )
    n_temporadas = st.select_slider(
        "Temporadas a simular", options=[100, 500, 1000, 2000, 5000], value=1000, key="n_temporadas_mc"
    )
    if st.button("🎲 Correr simulación de todo el torneo", type="primary"):
        with st.spinner(f"Simulando {n_temporadas:,} temporadas completas..."):
            st.session_state["resultado_montecarlo"] = simular_temporada_montecarlo(
                n=n_temporadas, peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO)

    if "resultado_montecarlo" in st.session_state:
        mc = st.session_state["resultado_montecarlo"]
        df_mc = pd.DataFrame([
            {"": flag(eq), "Equipo": eq, "Prob. Liguilla (%)": mc["prob_liguilla"][eq],
             "Prob. Campeón (%)": mc["prob_campeon"][eq],
             "Posición promedio": mc["posicion_promedio"][eq]}
            for eq in EQUIPOS
        ]).sort_values("Prob. Campeón (%)", ascending=False).reset_index(drop=True)

        st.dataframe(
            df_mc, use_container_width=True, hide_index=True,
            column_config={
                "Prob. Liguilla (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
                "Prob. Campeón (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
            },
        )
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**Top 10 — Probabilidad de Liguilla**")
            st.bar_chart(df_mc.nlargest(10, "Prob. Liguilla (%)").set_index("Equipo")["Prob. Liguilla (%)"])
        with col_c2:
            st.markdown("**Top 10 — Probabilidad de Campeón**")
            st.bar_chart(df_mc.nlargest(10, "Prob. Campeón (%)").set_index("Equipo")["Prob. Campeón (%)"])
    else:
        st.info("Presiona el botón para correr la simulación completa del torneo.")

# ─────────────────────────────────────────────────────────────────────────
# TAB — Modelo (informativo, NO editable)
# ─────────────────────────────────────────────────────────────────────────
with tab_info:
    st.markdown("#### ¿Cómo funciona el modelo?")
    st.markdown(f"""
El predictor usa **simulación Monte Carlo con distribución de Poisson** — {N_SIMS_PARTIDO:,} simulaciones
por partido, el mismo enfoque que casas de apuestas y modelos académicos serios.

**En cada simulación el modelo combina:**
- **Ataque/Defensa** — FUERZA_ATAQUE/FUERZA_DEFENSA de cada equipo, calibradas con el Clausura 2026 y
  **recalibradas solas** con cada resultado real que se agrega (media móvil exponencial, α=0.15)
- **Momentum vía Elo** — ajuste acotado (±8%) según cuánto se movió el Elo de cada equipo desde el
  arranque del torneo (fórmula Elo estándar de fútbol, con ventaja de local y multiplicador por goleada)
- **Forma real** — promedio real de goles anotados/recibidos en los partidos ya jugados (tope ±8%)
- **Corrección de sesgo del propio modelo** — ajuste acotado (±15%) basado en qué tan bien (o mal) ha
  venido prediciendo el modelo a CADA equipo en particular, comparando goles esperados guardados en el
  historial contra los goles reales — separado por local/visita. Solo se activa una vez que un equipo
  acumula 8+ partidos evaluados en ese rol; antes de eso, no tiene efecto.
- **Altitud** — bono de +{BONUS_ALTITUD_LOCAL} al λ del local si su ciudad está a ≥{ALTITUD_UMBRAL:,}m
  y el visitante no está aclimatado a la altura
- **Árbitro** — promedio real de tarjetas del árbitro asignado (cuando lo tenemos) vs. el promedio de
  liga ({PROMEDIO_LIGA_AMARILLAS} amarillas/partido)
- **Fatiga Leagues Cup** — reduce el λ ofensivo {(1-FACTOR_FATIGA_LEAGUES_CUP)*100:.0f}% si el equipo jugó
  Leagues Cup en los 7 días previos

Los factores de Ataque/Defensa, Momentum vía Elo y Forma real se recalculan solos cada vez que arranca la
app, reproduciendo todos los partidos que ya tienen resultado en `PARTIDOS` — no hay que tocar código ni
una base de datos aparte, basta con seguir agregando los resultados reales jornada a jornada. La
corrección de sesgo del propio modelo se recalcula igual de automático, leyendo el historial de
predicciones ya evaluadas de Supabase.

**¿Qué se recomienda como apuesta?**
Un umbral **dinámico**: entre 80% y 90% de probabilidad según qué tan avanzado está el torneo (más
partidos jugados = el modelo tiene más evidencia real y el umbral baja hasta el piso de 80%; al arranque
de temporada exige hasta 90%). Todo lo que llegue a ese umbral aparece en "Apuestas sugeridas" (por
partido) y en "Apuestas más fuertes de hoy" (todos los partidos del día) — una sola línea por rubro
(ej. solo la mejor de Total Goles), pero varios rubros distintos pueden aparecer juntos (ej. Total Goles
+ Tarjetas + Córners a la vez si los tres cumplen).

Mercados que evalúa: Resultado (1X2) · Doble Oportunidad (1X/X2) · Empate Sin Apuesta (DNB) · Hándicap
Asiático (-1.0/-2.0 del favorito) · Total de Goles (Over/Under) · Ambos Marcan · Tarjetas · Córners.
No incluye goles por mitades ni resultado al descanso — el modelo simula el partido completo con una sola
λ de Poisson por equipo, no reparte los goles entre el primer y segundo tiempo.

**Pesos actuales del modelo** (fijos, no ajustables desde la interfaz):

| Factor | Peso |
|---|---|
| ELO (ataque/defensa) | {PESO_ELO} |
| Altitud | {PESO_ALTITUD} |
| Árbitro | {PESO_ARBITRO} |

**Mercados de apuestas sugeridos:** Resultado (1X2), Doble Oportunidad, Total de Goles (Over/Under),
Ambos Marcan, Tarjetas totales (roja cuenta como 2 amarillas, igual que las casas de apuestas), y Córners.
""")
    st.markdown("---")
    n_jugados = n_partidos_procesados(PARTIDOS)
    st.markdown(f"#### ELO Ratings — 18 equipos (recalibrado con {n_jugados} partidos jugados)")
    sorted_elo = sorted(ELO_ACTUALIZADO.items(), key=lambda x: x[1], reverse=True)
    cols = st.columns(3)
    for i, (equipo, elo) in enumerate(sorted_elo):
        with cols[i % 3]:
            st.markdown(f"{flag(equipo)} **{equipo}** — `{round(elo, 1)}`")

    if n_jugados > 0:
        with st.expander(f"📈 Movimiento de Elo tras los últimos {n_jugados} partidos"):
            movimientos = resumen_movimiento_elo(ELO_BASE, ELO_ACTUALIZADO, top=10)
            for equipo, antes, despues, delta in movimientos:
                color = "#6b9b7d" if delta > 0 else ("#c0685a" if delta < 0 else "#888")
                signo = "+" if delta > 0 else ""
                st.markdown(
                    f"{flag(equipo)} **{equipo}** — {antes} → {despues} "
                    f"<span style='color:{color}'>({signo}{delta})</span>",
                    unsafe_allow_html=True,
                )
