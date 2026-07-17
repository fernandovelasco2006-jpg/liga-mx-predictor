import streamlit as st
import pandas as pd

from liga_mx_predictor_skeleton import (
    EQUIPOS, ELO, PARTIDOS, HORARIOS_PARTIDO, ARBITROS_LIGA_MX,
)
from liga_mx_algoritmo import (
    calcular_lambdas, simular_temporada, simular_temporada_montecarlo,
)

st.set_page_config(
    page_title="Liga MX · Apertura 2026 · Predictor",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Liga MX · Apertura 2026 · Predictor")
st.caption("Monte Carlo + ELO + Altitud + Árbitros — mismo enfoque que el predictor del Mundial 2026")

tab_jornada, tab_montecarlo, tab_config = st.tabs([
    "📅 Jornada Actual", "🎲 Probabilidades de Temporada (Montecarlo)", "⚙️ Configuración del Modelo",
])

# ─────────────────────────────────────────────────────────────────────────
# Estado de los sliders — se leen en cada rerun y se pasan como
# ARGUMENTOS EXPLÍCITOS a las funciones matemáticas. Nada de variables
# globales mutadas: así el cache de Streamlit y las corridas de Monte
# Carlo no se pisan entre sí.
# ─────────────────────────────────────────────────────────────────────────
with tab_config:
    st.markdown("### Pesos del modelo")
    st.markdown(
        "Ajusta cuánto pesa cada factor en el cálculo de goles esperados. "
        "**1.0 = calibración por defecto.** 0.0 = el factor no tiene efecto. "
        "2.0 = el doble de efecto."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        peso_elo = st.slider(
            "Peso ELO (ataque/defensa)", min_value=0.0, max_value=2.0, value=1.0, step=0.1,
            help="Qué tanto pesan las diferencias de fuerza entre equipos (derivadas del ELO). "
                 "En 0, todos los equipos son iguales de fuertes.",
        )
    with col2:
        peso_altitud = st.slider(
            "Peso Altitud", min_value=0.0, max_value=2.0, value=1.0, step=0.1,
            help="Bono de gol para equipos que juegan de local en ciudades altas "
                 "(Toluca, Pachuca, Querétaro, etc.) contra visitantes no aclimatados.",
        )
    with col3:
        peso_arbitro = st.slider(
            "Peso Árbitro", min_value=0.0, max_value=2.0, value=1.0, step=0.1,
            help="Qué tanto ajusta el promedio de tarjetas del árbitro asignado "
                 "el ritmo ofensivo esperado del partido.",
        )

    st.markdown("---")
    st.markdown("### Simulaciones Monte Carlo")
    n_simulaciones = st.slider(
        "Número de temporadas a simular", min_value=100, max_value=5000, value=1000, step=100,
        help="Más simulaciones = probabilidades más estables, pero tarda más.",
    )

    st.markdown("---")
    st.markdown("### Vista previa rápida del efecto de los pesos")
    col_a, col_b = st.columns(2)
    with col_a:
        equipo_local_preview = st.selectbox("Local", EQUIPOS, index=EQUIPOS.index("America"))
    with col_b:
        opciones_visita = [e for e in EQUIPOS if e != equipo_local_preview]
        equipo_visita_preview = st.selectbox("Visitante", opciones_visita, index=0)

    lam_h, lam_a = calcular_lambdas(
        equipo_local_preview, equipo_visita_preview,
        peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
    )
    c1, c2 = st.columns(2)
    c1.metric(f"λ {equipo_local_preview} (local)", f"{lam_h:.2f}")
    c2.metric(f"λ {equipo_visita_preview} (visita)", f"{lam_a:.2f}")

# ─────────────────────────────────────────────────────────────────────────
# TAB 1 — Jornada Actual
# ─────────────────────────────────────────────────────────────────────────
with tab_jornada:
    st.markdown("### Selecciona una jornada")
    jornadas_disponibles = sorted(set(p[2] for p in PARTIDOS))
    jornada_sel = st.selectbox("Jornada", jornadas_disponibles, index=0)

    partidos_jornada = [p for p in PARTIDOS if p[2] == jornada_sel]

    st.markdown(f"#### Jornada {jornada_sel} — {len(partidos_jornada)} partidos")
    for local, visit, jornada, estadio, resultado, arbitro in partidos_jornada:
        horario = HORARIOS_PARTIDO.get((local, visit), "Horario por confirmar")
        col_partido, col_pred = st.columns([2, 1])
        with col_partido:
            if resultado is not None:
                gh, ga = resultado
                st.markdown(f"**{local} {gh} - {ga} {visit}** ✅ (resultado real)")
            else:
                st.markdown(f"**{local}** vs **{visit}**")
            st.caption(f"📍 {estadio or 'Estadio TBD'} · 🕐 {horario} · 🧑‍⚖️ {arbitro or 'Árbitro por confirmar'}")
        with col_pred:
            if resultado is None:
                lam_h, lam_a = calcular_lambdas(
                    local, visit,
                    peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
                )
                st.caption(f"λ esperado: {lam_h:.2f} - {lam_a:.2f}")
        st.divider()

    st.markdown("### Tabla de posiciones (simulada con resultados reales + proyección)")
    if st.button("🔄 Recalcular tabla y Liguilla", key="btn_recalcular_jornada"):
        st.session_state["resultado_temporada"] = simular_temporada(
            peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
        )

    if "resultado_temporada" not in st.session_state:
        st.session_state["resultado_temporada"] = simular_temporada(
            peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
        )

    resultado = st.session_state["resultado_temporada"]
    df_tabla = pd.DataFrame(resultado["tabla_final"])
    df_tabla = df_tabla[["posicion", "equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "PTS"]]
    df_tabla.columns = ["#", "Equipo", "PJ", "PG", "PE", "PP", "GF", "GC", "DG", "Pts"]

    def resaltar_liguilla(fila):
        return ["background-color: #d4edda" if fila["#"] <= 8 else "" for _ in fila]

    st.dataframe(
        df_tabla.style.apply(resaltar_liguilla, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("🟩 Los primeros 8 lugares clasifican a la Liguilla")

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
# TAB 2 — Probabilidades de Temporada (Montecarlo)
# ─────────────────────────────────────────────────────────────────────────
with tab_montecarlo:
    st.markdown(f"### {n_simulaciones:,} temporadas simuladas")
    st.caption(
        "Corre la temporada completa (17 jornadas + Liguilla) muchas veces y agrega "
        "probabilidades de clasificar y ser campeón — el equivalente de liga regular "
        "a las simulaciones por partido del Mundial."
    )

    if st.button("🎲 Correr simulación Monte Carlo", type="primary"):
        with st.spinner(f"Simulando {n_simulaciones:,} temporadas completas..."):
            st.session_state["resultado_montecarlo"] = simular_temporada_montecarlo(
                n=n_simulaciones, peso_elo=peso_elo, peso_altitud=peso_altitud, peso_arbitro=peso_arbitro,
            )

    if "resultado_montecarlo" in st.session_state:
        mc = st.session_state["resultado_montecarlo"]
        df_mc = pd.DataFrame([
            {
                "Equipo": eq,
                "Prob. Liguilla (%)": mc["prob_liguilla"][eq],
                "Prob. Campeón (%)": mc["prob_campeon"][eq],
                "Posición promedio": mc["posicion_promedio"][eq],
            }
            for eq in EQUIPOS
        ]).sort_values("Prob. Campeón (%)", ascending=False).reset_index(drop=True)

        st.dataframe(
            df_mc.style.background_gradient(subset=["Prob. Campeón (%)"], cmap="Greens")
                       .background_gradient(subset=["Prob. Liguilla (%)"], cmap="Blues"),
            use_container_width=True,
            hide_index=True,
        )

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("**Top 10 — Probabilidad de Liguilla**")
            top10_liguilla = df_mc.nlargest(10, "Prob. Liguilla (%)").set_index("Equipo")
            st.bar_chart(top10_liguilla["Prob. Liguilla (%)"])
        with col_chart2:
            st.markdown("**Top 10 — Probabilidad de Campeón**")
            top10_campeon = df_mc.nlargest(10, "Prob. Campeón (%)").set_index("Equipo")
            st.bar_chart(top10_campeon["Prob. Campeón (%)"])
    else:
        st.info("Presiona el botón para correr la simulación con los pesos actuales.")
