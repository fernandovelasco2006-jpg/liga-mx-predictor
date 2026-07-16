# ─────────────────────────────────────────────────────────────────────────
# LIGA MX · APERTURA 2026 · PREDICTOR — ESQUELETO INICIAL
# Adaptado de la estructura del Mundial 2026 predictor.
# Todo lo marcado con "# ⚠️ FALTA:" necesita datos que no pude confirmar
# por búsqueda web — pídeselos a Perplexity o Google AI (Gemini), son
# mejores para agregación de estadísticas históricas puntuales.
# ─────────────────────────────────────────────────────────────────────────

# 18 equipos confirmados para Apertura 2026 (Atlante regresa, reemplaza a Mazatlán)
EQUIPOS = [
    "America", "Atlante", "Atlas", "Atletico San Luis", "Cruz Azul",
    "Guadalajara", "FC Juarez", "Leon", "Monterrey", "Necaxa",
    "Pachuca", "Puebla", "Pumas UNAM", "Queretaro", "Santos Laguna",
    "Tijuana", "Tigres", "Toluca",
]

# ─────────────────────────────────────────────────────────────────────────
# ALTITUD — sede de cada equipo (metros sobre el nivel del mar)
# Aquí SÍ importa mucho más que en el Mundial: tienes altura real cada
# jornada (Toluca 2,680m es más alto que México/Azteca), no solo en un
# puñado de partidos.
# ─────────────────────────────────────────────────────────────────────────
ALTITUD_EQUIPO = {
    "Toluca": 2680,
    "Puebla": 2135,
    "Pachuca": 2426,
    "Queretaro": 1820,
    "Atletico San Luis": 1860,
    "Leon": 1815,
    "Necaxa": 1878,           # Estadio Victoria, Aguascalientes
    "Guadalajara": 1566,      # Estadio Akron
    "Atlas": 1566,            # Estadio Jalisco / comparte ciudad con Chivas
    "Santos Laguna": 1120,    # Torreón
    "FC Juarez": 1137,
    "Monterrey": 540,
    "Tijuana": 20,
    # América, Cruz Azul y Atlante comparten el Estadio Banorte (CDMX)
    # este semestre — confirmado.
    "America": 2240,
    "Cruz Azul": 2240,
    "Atlante": 2240,
    # ⚠️ FALTA: Pumas UNAM — Estadio Olímpico Universitario, altitud
    #   aprox. 2,240m (CDMX) — puedes confirmarlo pero es casi seguro.
    "Pumas UNAM": 2240,
    "Tigres": 540,  # comparte ciudad con Monterrey (Nuevo León)
}

# ─────────────────────────────────────────────────────────────────────────
# JORNADA 1 — confirmada (16-18 julio 2026)
# Formato: (local, visitante, jornada, estadio, resultado, arbitro)
# ⚠️ FALTA: árbitros asignados a estos partidos — pídele a Perplexity:
#   "¿quiénes son los árbitros centrales asignados a cada partido de la
#   Jornada 1 del Apertura 2026 de Liga MX?"
# ─────────────────────────────────────────────────────────────────────────
PARTIDOS = [
    ("Necaxa",            "Atlante",            1, "Estadio Victoria",              None, None),
    ("Tijuana",           "Tigres",             1, "Estadio Caliente",              None, None),
    ("Atletico San Luis", "Cruz Azul",          1, "Estadio Alfonso Lastras",       None, None),
    ("Leon",              "Atlas",              1, "Estadio Nou Camp",              None, None),
    ("FC Juarez",         "Puebla",             1, "Estadio Olimpico Benito Juarez",None, None),
    ("Pumas UNAM",        "Pachuca",            1, "Estadio Olimpico Universitario",None, None),
    ("Monterrey",         "Santos Laguna",      1, "Estadio BBVA",                  None, None),
    ("Guadalajara",       "Toluca",             1, "Estadio Akron",                 None, None),
    ("Queretaro",         "America",            1, "Estadio Corregidora",           None, None),
    # ⚠️ FALTA: Jornadas 2 a 17. Pídele a Perplexity o Gemini:
    #   "Dame el calendario completo de las jornadas 2 a 17 del Apertura
    #   2026 de Liga MX, con fecha, hora (tiempo del centro de México) y
    #   estadio de cada partido, en formato de lista."
    #   Esto reemplaza tu HORARIOS_PARTIDO del Mundial.

    # ── Jornada 2 (21-26 julio 2026) — confirmada ──────────────────────
    ("Cruz Azul",          "Puebla",             2, None, None, None),
    ("Toluca",             "Pumas UNAM",         2, None, None, None),
    ("Tigres",             "Atletico San Luis",  2, None, None, None),
    ("Atlante",            "America",            2, None, None, None),
    ("Tijuana",            "Leon",               2, None, None, None),
    ("Guadalajara",        "FC Juarez",          2, None, None, None),
    ("Santos Laguna",      "Atlas",              2, None, None, None),
    ("Necaxa",             "Monterrey",          2, None, None, None),
    ("Pachuca",            "Queretaro",          2, None, None, None),

    # ── Jornada 3 (31 julio - 2 agosto 2026) — confirmada ──────────────
    ("Puebla",             "Guadalajara",        3, None, None, None),
    ("FC Juarez",          "Pumas UNAM",         3, None, None, None),
    ("Atletico San Luis",  "Tijuana",            3, None, None, None),
    ("Queretaro",          "Tigres",             3, None, None, None),
    ("Atlas",              "Monterrey",          3, None, None, None),
    ("Leon",               "Pachuca",            3, None, None, None),
    ("Cruz Azul",          "Atlante",            3, None, None, None),
    ("America",            "Santos Laguna",      3, None, None, None),
    ("Toluca",             "Necaxa",             3, None, None, None),

    # ── Jornada 4 (15-17 agosto 2026) — confirmada, tras parón Leagues Cup ──
    ("Atlante",            "Toluca",             4, None, None, None),
    ("Monterrey",          "FC Juarez",          4, None, None, None),
    ("Atlas",              "Tigres",             4, None, None, None),
    ("Pumas UNAM",         "Queretaro",          4, None, None, None),
    ("America",            "Atletico San Luis",  4, None, None, None),
    ("Santos Laguna",      "Guadalajara",        4, None, None, None),
    ("Tijuana",            "Cruz Azul",          4, None, None, None),
    ("Necaxa",             "Leon",               4, None, None, None),
    ("Pachuca",            "Puebla",             4, None, None, None),

    # ── Jornada 5 (21-23 agosto 2026) — COMPLETA ───────────────────────
    ("Puebla",             "Santos Laguna",      5, None, None, None),
    ("FC Juarez",          "America",            5, None, None, None),
    ("Guadalajara",        "Tijuana",            5, None, None, None),
    ("Queretaro",          "Toluca",             5, None, None, None),
    ("Pumas UNAM",         "Monterrey",          5, None, None, None),
    ("Cruz Azul",          "Atletico San Luis",  5, None, None, None),
    ("Tigres",             "Pachuca",            5, None, None, None),
    ("Leon",               "Necaxa",             5, None, None, None),
    # ⚠️ falta 1 partido de J5 (Atlante/Atlas no aparecen — probablemente
    #   tuvieron descanso o el dato no llegó completo, verificar)

    # ── Jornada 6 (28-30 agosto 2026) — COMPLETA ───────────────────────
    ("Atletico San Luis",  "FC Juarez",          6, None, None, None),
    ("Tijuana",            "Santos Laguna",      6, None, None, None),
    ("Necaxa",             "Queretaro",          6, None, None, None),
    ("Pachuca",            "Guadalajara",        6, None, None, None),
    ("America",            "Leon",               6, None, None, None),
    ("Toluca",             "Cruz Azul",          6, None, None, None),
    ("Puebla",             "Pumas UNAM",         6, None, None, None),
    ("Monterrey",          "Atlante",            6, None, None, None),
    ("Atlas",              "Tigres",             6, None, None, None),

    # ── Jornada 7 (11-13 sept 2026) — PARCIAL, faltan 2 partidos ───────
    ("Queretaro",          "Puebla",             7, None, None, None),
    ("FC Juarez",          "Tijuana",            7, None, None, None),
    ("Santos Laguna",      "Pachuca",            7, None, None, None),
    ("Guadalajara",        "Atletico San Luis",  7, None, None, None),
    ("Leon",               "Toluca",             7, None, None, None),
    ("Pumas UNAM",         "Necaxa",             7, None, None, None),
    ("Atlante",            "Atlas",              7, None, None, None),
    # ⚠️ faltan 2 partidos de J7 (movidos por fecha FIFA, según Perplexity)

    # ── Jornada 8 (12 sept 2026) — SOLO clásicos confirmados ───────────
    ("Cruz Azul",          "America",            8,  None, None, None),  # Clásico Joven
    ("Monterrey",          "Tigres",             8,  None, None, None),  # Clásico Regio
    # ⚠️ faltan 7 partidos de J8

    # ── Jornada 9 (19 sept 2026) — SOLO clásico confirmado ─────────────
    ("America",            "Guadalajara",        9,  None, None, None),  # Clásico Nacional
    # ⚠️ faltan 8 partidos de J9

    # ── Jornada 10 (2-4 oct 2026) — COMPLETA ───────────────────────────
    ("Puebla",             "FC Juarez",          10, None, None, None),
    ("Tijuana",            "Atlante",            10, None, None, None),
    ("Necaxa",             "Cruz Azul",          10, None, None, None),
    ("Tigres",             "Monterrey",          10, None, None, None),
    ("America",            "Pumas UNAM",         10, None, None, None),
    ("Toluca",             "Guadalajara",        10, None, None, None),
    ("Atlas",              "Santos Laguna",      10, None, None, None),
    ("Pachuca",            "Atletico San Luis",  10, None, None, None),
    ("Queretaro",          "Leon",               10, None, None, None),

    # ── Jornada 12 (16-18 oct 2026) — COMPLETA ─────────────────────────
    # ⚠️ OJO: en un mensaje anterior de Perplexity, el Clásico Tapatío
    #   aparecía como "Atlas vs Guadalajara" en la Jornada 11 (10 oct).
    #   Esta segunda respuesta, más detallada, lo ubica como
    #   "Guadalajara vs Atlas" en la Jornada 12 (17 oct). Usé esta
    #   segunda versión por ser más específica y venir acompañada del
    #   resto de la jornada completa, pero confírmalo con Perplexity:
    #   "¿el Clásico Tapatío del Apertura 2026 es Jornada 11 o 12, y
    #   quién es local?" antes de darlo por bueno.
    ("Atletico San Luis",  "Puebla",             12, None, None, None),
    ("FC Juarez",          "Leon",               12, None, None, None),
    ("Pachuca",            "Toluca",             12, None, None, None),
    ("Monterrey",          "Cruz Azul",          12, None, None, None),
    ("Guadalajara",        "Atlas",              12, None, None, None),  # Clásico Tapatío
    ("Pumas UNAM",         "Tijuana",            12, None, None, None),
    ("Atlante",            "Tigres",             12, None, None, None),
    ("Santos Laguna",      "Necaxa",             12, None, None, None),
    ("America",            "Queretaro",          12, None, None, None),

    # ── Jornada 13 (21-22 oct 2026) — fecha doble, entre semana — COMPLETA ──
    ("Cruz Azul",          "Pumas UNAM",         13, None, None, None),
    ("Tigres",             "FC Juarez",          13, None, None, None),
    ("Leon",               "Guadalajara",        13, None, None, None),
    ("Tijuana",            "America",            13, None, None, None),
    ("Toluca",             "Atletico San Luis",  13, None, None, None),
    ("Necaxa",             "Pachuca",            13, None, None, None),
    ("Puebla",             "Atlante",            13, None, None, None),
    ("Queretaro",          "Santos Laguna",      13, None, None, None),
    ("Atlas",              "Monterrey",          13, None, None, None),

    # ── Jornada 14 (24-26 oct 2026) — COMPLETA ─────────────────────────
    ("FC Juarez",          "Santos Laguna",      14, None, None, None),
    ("Guadalajara",        "Necaxa",             14, None, None, None),
    ("America",            "Monterrey",          14, None, None, None),
    ("Pumas UNAM",         "Leon",               14, None, None, None),
    ("Atlante",            "Queretaro",          14, None, None, None),
    ("Atletico San Luis",  "Tigres",             14, None, None, None),
    ("Tijuana",            "Atlas",              14, None, None, None),
    ("Cruz Azul",          "Puebla",             14, None, None, None),
    ("Toluca",             "Pachuca",            14, None, None, None),

    # ── Jornada 15 (30 oct - 1 nov 2026) — COMPLETA ────────────────────
    # ⚠️ OJO: Perplexity escribió literalmente "Mazatlán (Franquicia
    #   operada por Atlante) vs. Guadalajara" — Mazatlán ya no existe
    #   como equipo (ver conversación anterior), así que lo dejé como
    #   Atlante, pero es una señal de que la fuente está mezclando datos
    #   viejos. Verifica este partido específico con Perplexity antes
    #   de confiar en él: "¿Atlante vs Guadalajara se juega en Jornada
    #   15 del Apertura 2026, el 30 de octubre?"
    ("Necaxa",             "Tijuana",            15, None, None, None),
    ("Atlante",            "Guadalajara",        15, None, None, None),  # ⚠️ ver nota arriba
    ("Pachuca",            "America",            15, None, None, None),
    ("Monterrey",          "Pumas UNAM",         15, None, None, None),
    ("Tigres",             "Cruz Azul",          15, None, None, None),
    ("Toluca",             "Puebla",             15, None, None, None),
    ("Atlas",              "Atletico San Luis",  15, None, None, None),
    ("Santos Laguna",      "FC Juarez",          15, None, None, None),
    ("Leon",               "Queretaro",          15, None, None, None),

    # ⚠️ FALTA: Jornada 11 completa (probablemente 10 de octubre, pero
    #   ver nota del Clásico Tapatío arriba — puede que la J11 completa
    #   aclare la confusión). También faltan los partidos restantes de
    #   J7, J8 y J9, y toda la Jornada 17 (20-22 nov, cierre de fase
    #   regular).

    # ── Clásicos confirmados con hora exacta ───────────────────────────
    ("Pumas UNAM",         "America",            16, None, None, None),  # Clásico Capitalino
    # ⚠️ faltan los otros 8 partidos de J16, y toda la J17
    # J17: cierre de fase regular, 20-22 noviembre — partidos aún no listados
]

# ─────────────────────────────────────────────────────────────────────────
# HORARIOS_PARTIDO — igual estructura que usaste en el Mundial.
# Formato "YYYY-MM-DD HH:MM", tiempo del centro de México.
# ─────────────────────────────────────────────────────────────────────────
HORARIOS_PARTIDO = {
    # Jornada 1 (16-18 julio) — falta la hora exacta, solo tengo fecha/orden
    # Jornada 2
    ("Cruz Azul", "Puebla"):               "2026-07-21 18:00",
    ("Toluca", "Pumas UNAM"):              "2026-07-21 21:00",
    ("Tigres", "Atletico San Luis"):       "2026-07-24 19:00",
    ("Atlante", "America"):                "2026-07-24 20:00",
    ("Tijuana", "Leon"):                   "2026-07-24 20:00",
    ("Guadalajara", "FC Juarez"):          "2026-07-25 17:00",
    ("Santos Laguna", "Atlas"):            "2026-07-25 20:00",
    ("Necaxa", "Monterrey"):               "2026-07-26 17:00",
    ("Pachuca", "Queretaro"):              "2026-07-26 18:00",
    # Jornada 3
    ("Puebla", "Guadalajara"):             "2026-07-31 19:00",
    ("FC Juarez", "Pumas UNAM"):           "2026-07-31 20:00",
    ("Atletico San Luis", "Tijuana"):      "2026-07-31 21:00",
    ("Queretaro", "Tigres"):               "2026-08-01 17:00",
    ("Atlas", "Monterrey"):                "2026-08-01 18:00",
    ("Leon", "Pachuca"):                   "2026-08-01 18:00",
    ("Cruz Azul", "Atlante"):              "2026-08-01 20:00",
    ("America", "Santos Laguna"):          "2026-08-02 16:00",
    ("Toluca", "Necaxa"):                  "2026-08-02 18:00",
    # Jornada 4 (tras parón por Leagues Cup)
    ("Atlante", "Toluca"):                 "2026-08-15 17:00",
    ("Monterrey", "FC Juarez"):            "2026-08-15 19:00",
    ("Atlas", "Tigres"):                   "2026-08-15 20:00",
    ("Pumas UNAM", "Queretaro"):           "2026-08-16 11:00",
    ("America", "Atletico San Luis"):      "2026-08-16 16:00",
    ("Santos Laguna", "Guadalajara"):      "2026-08-16 19:00",
    ("Tijuana", "Cruz Azul"):              "2026-08-16 20:00",
    ("Necaxa", "Leon"):                    "2026-08-17 18:00",
    ("Pachuca", "Puebla"):                 "2026-08-17 21:00",
    # Jornada 5 — completa
    ("Puebla", "Santos Laguna"):           "2026-08-21 18:00",
    ("FC Juarez", "America"):              "2026-08-21 20:00",
    ("Guadalajara", "Tijuana"):            "2026-08-22 16:07",
    ("Queretaro", "Toluca"):               "2026-08-22 17:00",
    ("Pumas UNAM", "Monterrey"):           "2026-08-23 12:00",
    ("Cruz Azul", "Atletico San Luis"):    "2026-08-23 16:00",
    ("Tigres", "Pachuca"):                 "2026-08-23 18:00",
    ("Leon", "Necaxa"):                    "2026-08-23 20:00",
    # Jornada 6
    ("Atletico San Luis", "FC Juarez"):    "2026-08-28 19:00",
    ("Tijuana", "Santos Laguna"):          "2026-08-28 21:00",
    ("Necaxa", "Queretaro"):               "2026-08-29 17:00",
    ("Pachuca", "Guadalajara"):            "2026-08-29 19:00",
    ("America", "Leon"):                   "2026-08-29 21:00",
    ("Toluca", "Cruz Azul"):               "2026-08-30 12:00",
    ("Puebla", "Pumas UNAM"):              "2026-08-30 16:00",
    ("Monterrey", "Atlante"):              "2026-08-30 18:00",
    ("Atlas", "Tigres"):                   "2026-08-30 20:00",
    # Jornada 7 — parcial (faltan 2 partidos, movidos por fecha FIFA)
    ("Queretaro", "Puebla"):               "2026-09-11 19:00",
    ("FC Juarez", "Tijuana"):              "2026-09-11 21:00",
    ("Santos Laguna", "Pachuca"):          "2026-09-12 17:00",
    ("Guadalajara", "Atletico San Luis"):  "2026-09-12 19:05",
    ("Leon", "Toluca"):                    "2026-09-12 21:00",
    ("Pumas UNAM", "Necaxa"):              "2026-09-13 12:00",
    ("Atlante", "Atlas"):                  "2026-09-13 16:00",
    # Jornada 10
    ("Puebla", "FC Juarez"):               "2026-10-02 19:00",
    ("Tijuana", "Atlante"):                "2026-10-02 21:00",
    ("Necaxa", "Cruz Azul"):               "2026-10-03 17:00",
    ("Tigres", "Monterrey"):               "2026-10-03 19:00",
    ("America", "Pumas UNAM"):             "2026-10-03 21:05",
    ("Toluca", "Guadalajara"):             "2026-10-04 12:00",
    ("Atlas", "Santos Laguna"):            "2026-10-04 16:00",
    ("Pachuca", "Atletico San Luis"):      "2026-10-04 18:00",
    ("Queretaro", "Leon"):                 "2026-10-04 20:00",
    # Jornada 12
    ("Atletico San Luis", "Puebla"):       "2026-10-16 19:00",
    ("FC Juarez", "Leon"):                 "2026-10-16 21:00",
    ("Pachuca", "Toluca"):                 "2026-10-17 17:00",
    ("Monterrey", "Cruz Azul"):            "2026-10-17 19:00",
    ("Pumas UNAM", "Tijuana"):             "2026-10-18 12:00",
    ("Atlante", "Tigres"):                 "2026-10-18 16:00",
    ("Santos Laguna", "Necaxa"):           "2026-10-18 18:00",
    ("America", "Queretaro"):              "2026-10-18 20:00",
    # Jornada 13 — fecha doble entre semana
    ("Cruz Azul", "Pumas UNAM"):           "2026-10-21 18:30",
    ("Tigres", "FC Juarez"):               "2026-10-21 19:00",
    ("Leon", "Guadalajara"):               "2026-10-21 20:30",
    ("Tijuana", "America"):                "2026-10-21 21:00",
    ("Toluca", "Atletico San Luis"):       "2026-10-22 18:30",
    ("Necaxa", "Pachuca"):                 "2026-10-22 19:00",
    ("Puebla", "Atlante"):                 "2026-10-22 20:00",
    ("Queretaro", "Santos Laguna"):        "2026-10-22 20:30",
    ("Atlas", "Monterrey"):                "2026-10-22 21:00",
    # Jornada 14
    ("FC Juarez", "Santos Laguna"):        "2026-10-24 17:00",
    ("Guadalajara", "Necaxa"):             "2026-10-24 19:00",
    ("America", "Monterrey"):              "2026-10-24 21:05",
    ("Pumas UNAM", "Leon"):                "2026-10-25 12:00",
    ("Atlante", "Queretaro"):              "2026-10-25 16:00",
    ("Atletico San Luis", "Tigres"):       "2026-10-25 18:00",
    ("Tijuana", "Atlas"):                  "2026-10-25 20:00",
    ("Cruz Azul", "Puebla"):               "2026-10-26 19:00",
    ("Toluca", "Pachuca"):                 "2026-10-26 21:00",
    # Jornada 15
    ("Necaxa", "Tijuana"):                 "2026-10-30 19:00",
    ("Atlante", "Guadalajara"):            "2026-10-30 21:00",   # ⚠️ ver nota en PARTIDOS
    ("Pachuca", "America"):                "2026-10-31 17:00",
    ("Monterrey", "Pumas UNAM"):           "2026-10-31 19:00",
    ("Tigres", "Cruz Azul"):               "2026-10-31 21:00",
    ("Toluca", "Puebla"):                  "2026-11-01 12:00",
    ("Atlas", "Atletico San Luis"):        "2026-11-01 16:00",
    ("Santos Laguna", "FC Juarez"):        "2026-11-01 18:00",
    ("Leon", "Queretaro"):                 "2026-11-01 20:00",
    # Clásicos — horas confirmadas
    ("Cruz Azul", "America"):              "2026-09-12 21:05",   # Clásico Joven — J8
    ("Monterrey", "Tigres"):               "2026-09-12 19:00",   # Clásico Regio — J8
    ("America", "Guadalajara"):            "2026-09-19 21:05",   # Clásico Nacional — J9
    ("Guadalajara", "Atlas"):              "2026-10-17 21:05",   # Clásico Tapatío — J12 (ver nota)
    ("Pumas UNAM", "America"):             "2026-11-07 17:00",   # Clásico Capitalino — J16
}

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ FALTA POR COMPLETO — ELO / RATING DE FUERZA POR EQUIPO
# El Mundial usaba ranking FIFA de selecciones (fácil de encontrar ya
# calculado). Para clubes de Liga MX no hay un ELO "oficial" tan a la
# mano. Pídele a Perplexity o Gemini:
#   "Dame un ranking aproximado de fuerza (tipo ELO) de los 18 equipos
#   de Liga MX de cara al Apertura 2026, basado en su desempeño en el
#   Clausura 2026 (tabla general, diferencia de goles, resultados en
#   liguilla) y fichajes relevantes del mercado de verano 2026."
# Alternativa: usa ClubElo.com si tiene cobertura de Liga MX, o calcula
# tu propio ELO con resultados de los últimos 2-3 torneos (puedo
# ayudarte a programar esa lógica una vez tengas los resultados en un
# CSV/JSON).
# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# ELO — rating aproximado de arranque para Apertura 2026, basado en el
# desempeño del Clausura 2026 (posición, diferencia de goles, forma
# reciente) + ajuste específico para Atlante como recién ascendido.
# Conseguido vía Perplexity.
# ─────────────────────────────────────────────────────────────────────────
ELO = {
    "Guadalajara":        1710,  # Chivas
    "Pumas UNAM":         1705,
    "Cruz Azul":          1685,
    "Pachuca":            1675,
    "Toluca":             1670,
    "Tigres":             1655,
    "America":            1650,
    "Atlas":              1630,
    "Tijuana":            1620,
    "Monterrey":          1615,
    "Necaxa":             1600,
    "Queretaro":          1585,
    "FC Juarez":          1575,
    "Atletico San Luis":  1570,
    "Leon":               1565,
    "Puebla":             1545,
    "Atlante":            1435,  # recién ascendido, plantel Miguel Herrera — no heredado de Mazatlán
    "Santos Laguna":      1520,
}

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ FALTA POR COMPLETO — ÁRBITROS DE LIGA MX Y SU PROMEDIO DE TARJETAS
# Aquí tienes ventaja sobre el Mundial: son los mismos árbitros torneo
# tras torneo. Pídele a Perplexity o Gemini:
#   "Dame la lista de árbitros centrales activos en Liga MX para el
#   Apertura 2026, con su promedio de tarjetas amarillas y rojas por
#   partido en las últimas 2-3 temporadas, si hay datos disponibles."
# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# ⚠️ FALTA COMPLETAR — ÁRBITROS DE LIGA MX Y SU PROMEDIO DE TARJETAS
# Los 4 más activos del Clausura 2026, según Perplexity (Comisión de
# Árbitros FMF). Faltan los demás árbitros del padrón — pídele a
# Perplexity la lista completa cuando la necesites, o ve completándola
# jornada a jornada según quién pite cada partido (igual que hiciste
# manualmente en el Mundial).
# ─────────────────────────────────────────────────────────────────────────
ARBITROS_LIGA_MX = {
    # "Nombre": (promedio_amarillas, partidos_dirigidos_Clausura2026)
    "Daniel Quintero Huitron":         (4.8, 15),
    "Cesar Arturo Ramos Palazuelos":   (4.1, 14),
    "Adonai Escobedo Gonzalez":        (5.2, 11),
    "Ismael Rosario Lopez Peñuelas":   (4.5, 11),  # pitó la Final de Ida del Clausura 2026
}
ARBITRO_DEFAULT = (4.5, 0.15)  # promedio de los 4 conocidos, como fallback razonable

# ─────────────────────────────────────────────────────────────────────────
# CÓRNERS Y REMATES — proyección basada en plantillas actuales y estilo
# de juego de cada DT (Perplexity). Nota: son promedios proyectados, no
# datos duros de un torneo ya jugado (a diferencia del Mundial, donde
# tenías corners reales partido por partido).
# ─────────────────────────────────────────────────────────────────────────
CORNERS_EQUIPO = {
    "America":            5.8,
    "Tigres":             5.6,
    "Cruz Azul":          6.1,
    "Guadalajara":        5.4,
    "Monterrey":          5.5,
    "Pumas UNAM":         5.2,
    "Toluca":             5.0,
    "Pachuca":            5.3,
    "Atlas":              4.8,
    "Leon":               4.9,
    "Tijuana":            4.6,
    "Santos Laguna":      4.7,
    "Atletico San Luis":  4.4,
    "Necaxa":             4.3,
    "Atlante":            4.5,
    "Puebla":             4.1,
    "FC Juarez":          4.2,
    "Queretaro":          3.9,
}
CORNERS_DEFAULT = 4.5

# Remates totales y remates a puerta por equipo (mismo origen)
REMATES_TOTALES_EQUIPO = {
    "America": 14.5, "Tigres": 13.8, "Cruz Azul": 15.2, "Guadalajara": 13.1,
    "Monterrey": 14.0, "Pumas UNAM": 12.8, "Toluca": 13.5, "Pachuca": 13.2,
    "Atlas": 11.5, "Leon": 12.0, "Tijuana": 11.2, "Santos Laguna": 11.8,
    "Atletico San Luis": 10.9, "Necaxa": 10.5, "Atlante": 11.0,
    "Puebla": 9.8, "FC Juarez": 10.1, "Queretaro": 9.4,
}
REMATES_PUERTA_EQUIPO = {
    "America": 5.3, "Tigres": 4.9, "Cruz Azul": 5.5, "Guadalajara": 4.5,
    "Monterrey": 5.1, "Pumas UNAM": 4.4, "Toluca": 4.8, "Pachuca": 4.6,
    "Atlas": 3.9, "Leon": 4.1, "Tijuana": 3.8, "Santos Laguna": 4.0,
    "Atletico San Luis": 3.7, "Necaxa": 3.5, "Atlante": 3.6,
    "Puebla": 3.2, "FC Juarez": 3.3, "Queretaro": 3.0,
}
REMATES_PUERTA_DEFAULT = 3.5

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ FALTA — BAJAS / LESIONES POR EQUIPO
# Esto se actualiza jornada a jornada, igual que hiciste en el Mundial.
# Pídele a Perplexity: "¿qué jugadores clave están lesionados o
# suspendidos de cara a la Jornada X del Apertura 2026 de Liga MX,
# equipo por equipo?" — mejor pedirlo semana a semana que de una vez.
# ─────────────────────────────────────────────────────────────────────────
BAJAS = {}

# ─────────────────────────────────────────────────────────────────────────
# NOTAS DE FORMATO — diferencias clave vs. el Mundial que ya tenías
# ─────────────────────────────────────────────────────────────────────────
# 1. NO hay grupos: son 17 jornadas de todos-contra-todos a un solo
#    partido. Tu función calcular_lambdas() se puede reusar casi igual,
#    pero la "tabla general" ahora se calcula acumulando puntos de las
#    17 jornadas (3 pts victoria, 1 empate, 0 derrota).
# 2. Liguilla: cuartos, semis y FINAL se juegan a IDA Y VUELTA (no
#    partido único con penales directo como en el Mundial). Tu lógica
#    de "probabilidad de clasificación" necesita sumar el marcador
#    global de ambos partidos, y solo ir a penales si hay empate en
#    el marcador agregado.
# 3. Sin Play-In: los 8 primeros de la tabla general avanzan directo a
#    cuartos — no hay ronda eliminatoria extra para el 7°-10° lugar
#    como en torneos anteriores.
# 4. Fixture congestion: pausa del 4-13 agosto por fase de grupos de
#    Leagues Cup 2026 — considera un factor de fatiga/rotación para
#    equipos que jueguen ambos torneos en semanas cercanas.
