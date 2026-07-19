import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, timezone

from liga_mx_predictor_skeleton import (
    EQUIPOS, ELO, ALTITUD_EQUIPO, PARTIDOS, HORARIOS_PARTIDO, ARBITROS_LIGA_MX,
    ARBITRO_DEFAULT, CORNERS_EQUIPO,
)
from liga_mx_algoritmo import (
    calcular_lambdas, simular_temporada, simular_temporada_montecarlo,
    simular_partido, analizar_apuestas, armar_parlay,
    ALTITUD_UMBRAL, BONUS_ALTITUD_LOCAL, FACTOR_FATIGA_LEAGUES_CUP,
    PROMEDIO_LIGA_AMARILLAS, PROMEDIO_LIGA_ROJAS,
)

try:
    from liga_mx_supabase import (
        guardar_prediccion, guardar_apuestas, cargar_historial_apuestas,
        calcular_stats_apuestas, actualizar_aciertos_pendientes,
    )
    SUPABASE_MODULO_DISPONIBLE = True
except ImportError:
    SUPABASE_MODULO_DISPONIBLE = False

try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL_LIGAMX", None)
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY_LIGAMX", None)
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL_LIGAMX", None)
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY_LIGAMX", None)

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
  <div class="hero-sub">Monte Carlo · 10,000,000 simulaciones · ELO + Altitud + Árbitro</div>
</div>""", unsafe_allow_html=True)

BANDERAS_EQUIPO = {
    "America": "🦅", "Atlante": "🔵", "Atlas": "🔴", "Atletico San Luis": "🔴",
    "Cruz Azul": "🔵", "Guadalajara": "🔴", "FC Juarez": "🟢", "Leon": "🟢",
    "Monterrey": "🔵", "Necaxa": "⚪", "Pachuca": "🟡", "Puebla": "🔵",
    "Pumas UNAM": "🐾", "Queretaro": "⚫", "Santos Laguna": "⚪",
    "Tijuana": "🔴", "Tigres": "🟠", "Toluca": "🔴",
}

def flag(t):
    return BANDERAS_EQUIPO.get(t, "⚽")

def tag(cls, txt):
    return f'<span class="tag {cls}">{txt}</span>'

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
        except Exception:
            pass
    st.session_state["aciertos_lm_actualizados"] = True


# ─────────────────────────────────────────────────────────────────────────
# APUESTAS MÁS FUERTES DE HOY — arriba de todo, se calcula solo al abrir
# la página. Cacheado 1 hora para no re-simular 10M por cada visitante.
# ─────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _simular_partido_cached(local, visit, n, peso_elo, peso_altitud, peso_arbitro):
    return simular_partido(local, visit, n=n, peso_elo=peso_elo,
                            peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)


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

if partidos_hoy_global:
    with st.expander(f"🎰 APUESTAS MÁS FUERTES DE HOY ({hoy}) — Click para ver", expanded=True):
        st.caption("Se calcula automáticamente al abrir la página · solo señales de confianza ALTA")
        total_apuestas_hoy = 0
        for local, visit, jornada, estadio, resultado, arbitro in partidos_hoy_global:
            horario = HORARIOS_PARTIDO.get((local, visit), "")
            hora_str = horario[11:] if horario else ""
            r_hoy = _simular_partido_cached(local, visit, N_SIMS_PARTIDO, PESO_ELO, PESO_ALTITUD, PESO_ARBITRO)
            sugs_hoy = analizar_apuestas(local, visit, r_hoy)
            _registrar_apuestas_sesion(local, visit, jornada, sugs_hoy, r=r_hoy, resultado_real=None)
            sugs_alta_hoy = [s for s in sugs_hoy if s["nivel"] == "ALTA"]
            if not sugs_alta_hoy:
                continue
            total_apuestas_hoy += len(sugs_alta_hoy)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;margin:0.8rem 0 0.4rem;'
                f'padding-bottom:0.3rem;border-bottom:1px solid #1f4a2e">'
                f'<span style="font-size:0.82rem;color:#e8f0ea;font-weight:600">'
                f'{flag(local)} {local} vs {flag(visit)} {visit}</span>'
                f'<span style="font-size:0.68rem;color:#6b9b7d">⏰ {hora_str}h · Jornada {jornada}</span></div>',
                unsafe_allow_html=True,
            )
            cols_hoy = st.columns(min(len(sugs_alta_hoy), 3))
            for i_ap, ap in enumerate(sugs_alta_hoy[:3]):
                with cols_hoy[i_ap % 3]:
                    st.markdown(
                        f'<div class="bet-card bet-card-alta"><div style="font-size:0.55rem;color:#6b9b7d;'
                        f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                        f'<div style="font-size:0.88rem;color:#e8f0ea;margin:0.2rem 0;font-weight:600">{ap["seleccion"]}</div>'
                        f'<div style="font-size:0.62rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div></div>',
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


tab_pred, tab_res, tab_apuestas, tab_hist, tab_hist_ap, tab_info = st.tabs([
    "🎯 Predictor", "📊 Resultados reales", "🎰 Apuestas", "📈 Historial", "🎲 Apuestas Hist.", "⚙️ Modelo",
])

# ─────────────────────────────────────────────────────────────────────────
# TAB — Predictor
# ─────────────────────────────────────────────────────────────────────────
with tab_pred:
    col_izq, col_der = st.columns([1, 2.5], gap="large")
    with col_izq:
        st.markdown("#### Elige el partido")
        jornadas = sorted(set(p[2] for p in PARTIDOS))
        jornada_sel = st.selectbox("Jornada", jornadas, index=0, key="jornada_pred")
        partidos_j = [p for p in PARTIDOS if p[2] == jornada_sel]
        opciones = {f"{flag(p[0])} {p[0]} vs {flag(p[1])} {p[1]}": i for i, p in enumerate(partidos_j)}
        lbl_sel = st.selectbox("Partido", list(opciones.keys()), key="partido_pred")
        idx_sel = opciones[lbl_sel]
        local, visit, jornada, estadio, resultado_real, arbitro = partidos_j[idx_sel]

        st.markdown("---")
        st.caption(f"⚡ {N_SIMS_PARTIDO:,} simulaciones")
        btn = st.button("⚽ Simular partido", key="btn_simular")

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
                r = simular_partido(local, visit, n=N_SIMS_PARTIDO,
                                     peso_elo=PESO_ELO, peso_altitud=PESO_ALTITUD, peso_arbitro=PESO_ARBITRO)

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

            st.markdown("<br>", unsafe_allow_html=True)
            sugs = analizar_apuestas(local, visit, r)
            _registrar_apuestas_sesion(local, visit, jornada, sugs, r=r, resultado_real=resultado_real)
            if sugs:
                st.markdown('<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;'
                            'letter-spacing:2px;color:#e5007d;margin-bottom:0.75rem">🎰 APUESTAS SUGERIDAS</div>',
                            unsafe_allow_html=True)
                cols_ap = st.columns(min(len(sugs), 3))
                for i_ap, ap in enumerate(sugs[:3]):
                    with cols_ap[i_ap]:
                        cls = "bet-card-alta" if ap["nivel"] == "ALTA" else "bet-card-media"
                        st.markdown(
                            f'<div class="bet-card {cls}"><div style="font-size:0.6rem;color:#6b9b7d;'
                            f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                            f'<div style="font-size:0.95rem;color:#e8f0ea;margin:0.3rem 0;font-weight:600">{ap["seleccion"]}</div>'
                            f'<div style="font-size:0.65rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div>'
                            f'<div style="font-size:0.6rem;color:#6b9b7d;margin-top:0.3rem">{ap["nota"]}</div></div>',
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
            r = _simular_partido_cached(local, visit, N_SIMS_PARTIDO, PESO_ELO, PESO_ALTITUD, PESO_ARBITRO)
            sugs_todas = analizar_apuestas(local, visit, r)
            sugs = [s for s in sugs_todas if s["nivel"] == "ALTA"]
            if not sugs:
                st.caption("Sin señales de confianza ALTA para este partido.")
            else:
                cols_ap = st.columns(min(len(sugs), 3))
                for i_ap, ap in enumerate(sugs[:3]):
                    with cols_ap[i_ap % 3]:
                        st.markdown(
                            f'<div class="bet-card bet-card-alta"><div style="font-size:0.55rem;color:#6b9b7d;'
                            f'letter-spacing:2px;text-transform:uppercase">{ap["mercado"]}</div>'
                            f'<div style="font-size:0.9rem;color:#e8f0ea;margin:0.2rem 0;font-weight:600">{ap["seleccion"]}</div>'
                            f'<div style="font-size:0.65rem;color:#4ade80">{ap["confianza"]:.0f}% confianza</div></div>',
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
# TAB — Modelo (informativo, NO editable)
# ─────────────────────────────────────────────────────────────────────────
with tab_info:
    st.markdown("#### ¿Cómo funciona el modelo?")
    st.markdown(f"""
El predictor usa **simulación Monte Carlo con distribución de Poisson** — {N_SIMS_PARTIDO:,} simulaciones
por partido, el mismo enfoque que casas de apuestas y modelos académicos serios.

**En cada simulación el modelo combina:**
- **Ataque/Defensa** — derivado del ELO de cada equipo (⚠️ placeholder hasta tener goles reales del Clausura 2026)
- **Altitud** — bono de +{BONUS_ALTITUD_LOCAL} al λ del local si su ciudad está a ≥{ALTITUD_UMBRAL:,}m
  y el visitante no está aclimatado a la altura
- **Árbitro** — promedio real de tarjetas del árbitro asignado (cuando lo tenemos) vs. el promedio de
  liga ({PROMEDIO_LIGA_AMARILLAS} amarillas/partido)
- **Fatiga Leagues Cup** — reduce el λ ofensivo {(1-FACTOR_FATIGA_LEAGUES_CUP)*100:.0f}% si el equipo jugó
  Leagues Cup en los 7 días previos

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
    st.markdown("#### ELO Ratings — 18 equipos")
    sorted_elo = sorted(ELO.items(), key=lambda x: x[1], reverse=True)
    cols = st.columns(3)
    for i, (equipo, elo) in enumerate(sorted_elo):
        with cols[i % 3]:
            st.markdown(f"{flag(equipo)} **{equipo}** — `{elo}`")
