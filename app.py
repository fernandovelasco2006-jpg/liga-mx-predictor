import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

from liga_mx_predictor_skeleton import (
    EQUIPOS, ELO, ALTITUD_EQUIPO, PARTIDOS, HORARIOS_PARTIDO, ARBITROS_LIGA_MX,
)
from liga_mx_algoritmo import (
    calcular_lambdas, simular_temporada, simular_temporada_montecarlo,
    simular_partido, analizar_apuestas, armar_parlay,
)

st.set_page_config(
    page_title="Liga MX · Apertura 2026 · Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────
# ESTILO — mismo lenguaje visual que el Mundial-predictor, recoloreado:
# verde/blanco/rojo (México) + magenta Liga MX como acento.
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
  <div class="hero-sub">Monte Carlo · hasta 10,000,000 simulaciones · ELO + Altitud + Árbitro</div>
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

# ─────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────
tab_pred, tab_apuestas, tab_tabla, tab_mc, tab_config = st.tabs([
    "🎯 Predictor", "🎰 Apuestas del Día", "📊 Tabla / Liguilla",
    "🎲 Montecarlo Temporada", "⚙️ Configuración",
])

# ── Configuración (se define primero porque los otros tabs la usan) ──────
with tab_config:
    st.markdown("### Pesos del modelo")
    st.caption("1.0 = calibración por defecto. 0.0 = sin efecto. 2.0 = doble efecto.")
    col1, col2, col3 = st.columns(3)
    with col1:
        peso_elo = st.slider("Peso ELO (ataque/defensa)", 0.0, 2.0, 1.0, 0.1)
    with col2:
        peso_altitud = st.slider("Peso Altitud", 0.0, 2.0, 1.0, 0.1)
    with col3:
        peso_arbitro = st.slider("Peso Árbitro", 0.0, 2.0, 1.0, 0.1)
    st.markdown("---")
    N_SIMS_PARTIDO = 10_000_000  # fijo, igual que en el Mundial
    n_temporadas_mc = st.slider("Temporadas a simular (Montecarlo)", 100, 5000, 1000, 100)

# ─────────────────────────────────────────────────────────────────────────
# TAB — Predictor (estilo Mundial: elige partido, simula N veces)
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
        estado_tag = '<span class="tag tag-played">✓ Jugado</span>' if resultado_real else '<span class="tag tag-pending">⏳ Por jugarse</span>'
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
                                     peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)

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
                f'Árbitro: {r["arbitro"]} · Pesos: ELO={peso_elo} Altitud={peso_altitud} Árbitro={peso_arbitro}</div>',
                unsafe_allow_html=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)
            sugs = analizar_apuestas(local, visit, r)
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
                        f'<div style="background:linear-gradient(135deg,#1a1500,#2a2000);'
                        f'border:1px solid #e5007d;border-radius:10px;padding:0.8rem 1rem;margin-top:0.75rem">'
                        f'<span style="font-size:0.6rem;color:#e5007d;letter-spacing:2px">💛 PARLAY SUGERIDO</span>'
                        f'<div style="font-size:0.85rem;color:#e5007d;margin:0.2rem 0">{parlay["texto"]}</div>'
                        f'<div style="font-size:0.65rem;color:#8fbfa0">Prob. combinada: '
                        f'<b style="color:#e5007d">{parlay["prob_combinada"]:.1f}%</b></div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("Sin señales claras de apuesta para este partido — modelo conservador.")

# ─────────────────────────────────────────────────────────────────────────
# TAB — Apuestas del Día (estilo Mundial: expander con partidos de hoy)
# ─────────────────────────────────────────────────────────────────────────
with tab_apuestas:
    st.markdown("### 🎰 Apuestas más fuertes de hoy")
    tz_mx = timezone(timedelta(hours=-6))
    hoy = datetime.now(tz_mx).strftime("%Y-%m-%d")

    partidos_hoy = []
    for p in PARTIDOS:
        local, visit, jornada, estadio, resultado, arbitro = p
        if resultado is not None:
            continue
        horario = HORARIOS_PARTIDO.get((local, visit))
        if horario and horario[:10] == hoy:
            partidos_hoy.append(p)

    if not partidos_hoy:
        st.info(f"No hay partidos programados para hoy ({hoy}). Explora otras jornadas en el tab Predictor.")
    else:
        for local, visit, jornada, estadio, resultado, arbitro in partidos_hoy:
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
            with st.spinner(f"Simulando {N_SIMS_PARTIDO:,} veces..."):
                r = simular_partido(local, visit, n=N_SIMS_PARTIDO, peso_elo=peso_elo,
                                     peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)
            sugs = [s for s in analizar_apuestas(local, visit, r) if s["nivel"] == "ALTA"]
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
                        f'<div style="background:linear-gradient(135deg,#1a1500,#2a2000);'
                        f'border:1px solid #e5007d;border-radius:10px;padding:0.6rem 0.9rem;margin-top:0.5rem">'
                        f'<span style="font-size:0.55rem;color:#e5007d;letter-spacing:2px">💛 PARLAY</span>'
                        f'<div style="font-size:0.78rem;color:#e5007d;margin:0.15rem 0">{parlay["texto"]}</div>'
                        f'<div style="font-size:0.6rem;color:#8fbfa0">Prob. combinada: '
                        f'<b style="color:#e5007d">{parlay["prob_combinada"]:.1f}%</b></div></div>',
                        unsafe_allow_html=True,
                    )
    st.markdown('<div style="font-size:0.65rem;color:#4a5568;padding-top:1rem;border-top:1px solid #1f4a2e;'
                'margin-top:1rem">⚠️ Solo informativo · Apuesta responsablemente</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────
# TAB — Tabla / Liguilla
# ─────────────────────────────────────────────────────────────────────────
with tab_tabla:
    st.markdown("### Tabla de posiciones (resultados reales + proyección)")
    if st.button("🔄 Recalcular tabla y Liguilla") or "resultado_temporada" not in st.session_state:
        st.session_state["resultado_temporada"] = simular_temporada(
            peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)

    resultado = st.session_state["resultado_temporada"]
    df_tabla = pd.DataFrame(resultado["tabla_final"])
    df_tabla = df_tabla[["posicion", "equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "PTS"]]
    df_tabla.columns = ["#", "Equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "Pts"]
    st.dataframe(
        df_tabla,
        use_container_width=True, hide_index=True,
        column_config={"#": st.column_config.NumberColumn(width="small")},
    )
    st.caption("Los primeros 8 lugares (arriba) clasifican a la Liguilla")

    st.markdown("### Liguilla simulada")
    liguilla = resultado["liguilla"]
    col_cf, col_sf, col_f = st.columns(3)
    with col_cf:
        st.markdown("**Cuartos de Final**")
        for serie in liguilla["cuartos"]:
            st.markdown(f"- {serie['marcador_global']} → **{serie['ganador']}**")
    with col_sf:
        st.markdown("**Semifinales**")
        for serie in liguilla["semis"]:
            st.markdown(f"- {serie['marcador_global']} → **{serie['ganador']}**")
    with col_f:
        st.markdown("**Final**")
        st.markdown(f"- {liguilla['final']['marcador_global']}")
        st.success(f"🏆 Campeón: {liguilla['campeon']}")

# ─────────────────────────────────────────────────────────────────────────
# TAB — Montecarlo Temporada
# ─────────────────────────────────────────────────────────────────────────
with tab_mc:
    st.markdown(f"### {n_temporadas_mc:,} temporadas simuladas")
    if st.button("🎲 Correr simulación Montecarlo", type="primary"):
        with st.spinner(f"Simulando {n_temporadas_mc:,} temporadas completas..."):
            st.session_state["resultado_montecarlo"] = simular_temporada_montecarlo(
                n=n_temporadas_mc, peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro)

    if "resultado_montecarlo" in st.session_state:
        mc = st.session_state["resultado_montecarlo"]
        df_mc = pd.DataFrame([
            {"Equipo": eq, "Prob. Liguilla (%)": mc["prob_liguilla"][eq],
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
        st.info("Presiona el botón para correr la simulación con los pesos actuales.")
