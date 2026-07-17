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
# ─────────────────────────────────────────────────────────────────────────
# PARTIDOS — calendario OFICIAL completo (153 partidos, 17 jornadas),
# verificado automáticamente: cada equipo juega exactamente 1 vez por
# jornada, sin duplicados ni huecos. Estadio = casa del equipo local
# (América/Cruz Azul/Atlante comparten Estadio Banorte).
# ─────────────────────────────────────────────────────────────────────────
PARTIDOS = [
    ('Necaxa', 'Atlante', 1, 'Estadio Victoria', None, None),
    ('Tijuana', 'Tigres', 1, 'Estadio Caliente', None, None),
    ('Atletico San Luis', 'Cruz Azul', 1, 'Estadio Alfonso Lastras', None, None),
    ('Leon', 'Atlas', 1, 'Estadio Nou Camp', None, None),
    ('FC Juarez', 'Puebla', 1, 'Estadio Olimpico Benito Juarez', None, None),
    ('Pumas UNAM', 'Pachuca', 1, 'Estadio Olimpico Universitario', None, None),
    ('Guadalajara', 'Toluca', 1, 'Estadio Akron', None, None),
    ('Monterrey', 'Santos Laguna', 1, 'Estadio BBVA', None, None),
    ('Queretaro', 'America', 1, 'Estadio Corregidora', None, None),
    ('Cruz Azul', 'Puebla', 2, 'Estadio Banorte', None, None),
    ('Toluca', 'Pumas UNAM', 2, 'Estadio Nemesio Diez', None, None),
    ('Tigres', 'Atletico San Luis', 2, 'Estadio Universitario', None, None),
    ('Tijuana', 'Leon', 2, 'Estadio Caliente', None, None),
    ('Atlante', 'America', 2, 'Estadio Banorte', None, None),
    ('Guadalajara', 'FC Juarez', 2, 'Estadio Akron', None, None),
    ('Santos Laguna', 'Atlas', 2, 'Estadio TSM Corona', None, None),
    ('Necaxa', 'Monterrey', 2, 'Estadio Victoria', None, None),
    ('Pachuca', 'Queretaro', 2, 'Estadio Hidalgo', None, None),
    ('Puebla', 'Guadalajara', 3, 'Estadio Cuauhtemoc', None, None),
    ('FC Juarez', 'Pumas UNAM', 3, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atletico San Luis', 'Tijuana', 3, 'Estadio Alfonso Lastras', None, None),
    ('Queretaro', 'Tigres', 3, 'Estadio Corregidora', None, None),
    ('Atlas', 'Monterrey', 3, 'Estadio Jalisco', None, None),
    ('Leon', 'Pachuca', 3, 'Estadio Nou Camp', None, None),
    ('Cruz Azul', 'Atlante', 3, 'Estadio Banorte', None, None),
    ('America', 'Santos Laguna', 3, 'Estadio Banorte', None, None),
    ('Toluca', 'Necaxa', 3, 'Estadio Nemesio Diez', None, None),
    ('Atlante', 'Toluca', 4, 'Estadio Banorte', None, None),
    ('Monterrey', 'FC Juarez', 4, 'Estadio BBVA', None, None),
    ('Atlas', 'Tigres', 4, 'Estadio Jalisco', None, None),
    ('Pumas UNAM', 'Queretaro', 4, 'Estadio Olimpico Universitario', None, None),
    ('America', 'Atletico San Luis', 4, 'Estadio Banorte', None, None),
    ('Santos Laguna', 'Guadalajara', 4, 'Estadio TSM Corona', None, None),
    ('Tijuana', 'Cruz Azul', 4, 'Estadio Caliente', None, None),
    ('Necaxa', 'Leon', 4, 'Estadio Victoria', None, None),
    ('Pachuca', 'Puebla', 4, 'Estadio Hidalgo', None, None),
    ('Puebla', 'Santos Laguna', 5, 'Estadio Cuauhtemoc', None, None),
    ('FC Juarez', 'America', 5, 'Estadio Olimpico Benito Juarez', None, None),
    ('Guadalajara', 'Tijuana', 5, 'Estadio Akron', None, None),
    ('Queretaro', 'Toluca', 5, 'Estadio Corregidora', None, None),
    ('Leon', 'Monterrey', 5, 'Estadio Nou Camp', None, None),
    ('Tigres', 'Atlante', 5, 'Estadio Universitario', None, None),
    ('Cruz Azul', 'Atlas', 5, 'Estadio Banorte', None, None),
    ('Atletico San Luis', 'Pachuca', 5, 'Estadio Alfonso Lastras', None, None),
    ('Pumas UNAM', 'Necaxa', 5, 'Estadio Olimpico Universitario', None, None),
    ('Atlante', 'Leon', 6, 'Estadio Banorte', None, None),
    ('Necaxa', 'Cruz Azul', 6, 'Estadio Victoria', None, None),
    ('Tijuana', 'Pumas UNAM', 6, 'Estadio Caliente', None, None),
    ('Pachuca', 'Guadalajara', 6, 'Estadio Hidalgo', None, None),
    ('Atlas', 'Queretaro', 6, 'Estadio Jalisco', None, None),
    ('America', 'Puebla', 6, 'Estadio Banorte', None, None),
    ('Santos Laguna', 'Tigres', 6, 'Estadio TSM Corona', None, None),
    ('Toluca', 'FC Juarez', 6, 'Estadio Nemesio Diez', None, None),
    ('Monterrey', 'Atletico San Luis', 6, 'Estadio BBVA', None, None),
    ('Puebla', 'Toluca', 7, 'Estadio Cuauhtemoc', None, None),
    ('FC Juarez', 'Pachuca', 7, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atletico San Luis', 'Guadalajara', 7, 'Estadio Alfonso Lastras', None, None),
    ('Queretaro', 'Monterrey', 7, 'Estadio Corregidora', None, None),
    ('Tigres', 'Necaxa', 7, 'Estadio Universitario', None, None),
    ('America', 'Tijuana', 7, 'Estadio Banorte', None, None),
    ('Atlas', 'Atlante', 7, 'Estadio Jalisco', None, None),
    ('Pumas UNAM', 'Leon', 7, 'Estadio Olimpico Universitario', None, None),
    ('Cruz Azul', 'Santos Laguna', 7, 'Estadio Banorte', None, None),
    ('Necaxa', 'Puebla', 8, 'Estadio Victoria', None, None),
    ('Atlante', 'Pachuca', 8, 'Estadio Banorte', None, None),
    ('Tijuana', 'Queretaro', 8, 'Estadio Caliente', None, None),
    ('Cruz Azul', 'America', 8, 'Estadio Banorte', None, None),
    ('Toluca', 'Atlas', 8, 'Estadio Nemesio Diez', None, None),
    ('Leon', 'Atletico San Luis', 8, 'Estadio Nou Camp', None, None),
    ('Santos Laguna', 'FC Juarez', 8, 'Estadio TSM Corona', None, None),
    ('Guadalajara', 'Pumas UNAM', 8, 'Estadio Akron', None, None),
    ('Monterrey', 'Tigres', 8, 'Estadio BBVA', None, None),
    ('Puebla', 'Atlante', 9, 'Estadio Cuauhtemoc', None, None),
    ('FC Juarez', 'Tigres', 9, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atletico San Luis', 'Necaxa', 9, 'Estadio Alfonso Lastras', None, None),
    ('Atlas', 'Pumas UNAM', 9, 'Estadio Jalisco', None, None),
    ('Monterrey', 'Cruz Azul', 9, 'Estadio BBVA', None, None),
    ('America', 'Guadalajara', 9, 'Estadio Banorte', None, None),
    ('Toluca', 'Santos Laguna', 9, 'Estadio Nemesio Diez', None, None),
    ('Pachuca', 'Tijuana', 9, 'Estadio Hidalgo', None, None),
    ('Queretaro', 'Leon', 9, 'Estadio Corregidora', None, None),
    ('Atlante', 'Monterrey', 10, 'Estadio Banorte', None, None),
    ('Tijuana', 'Atlas', 10, 'Estadio Caliente', None, None),
    ('Guadalajara', 'Queretaro', 10, 'Estadio Akron', None, None),
    ('Santos Laguna', 'Pachuca', 10, 'Estadio TSM Corona', None, None),
    ('Tigres', 'Puebla', 10, 'Estadio Universitario', None, None),
    ('Cruz Azul', 'Toluca', 10, 'Estadio Banorte', None, None),
    ('Pumas UNAM', 'Atletico San Luis', 10, 'Estadio Olimpico Universitario', None, None),
    ('Leon', 'FC Juarez', 10, 'Estadio Nou Camp', None, None),
    ('Necaxa', 'America', 10, 'Estadio Victoria', None, None),
    ('Queretaro', 'Atlante', 11, 'Estadio Corregidora', None, None),
    ('Puebla', 'Leon', 11, 'Estadio Cuauhtemoc', None, None),
    ('Tigres', 'Toluca', 11, 'Estadio Universitario', None, None),
    ('FC Juarez', 'Tijuana', 11, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atlas', 'Guadalajara', 11, 'Estadio Jalisco', None, None),
    ('America', 'Monterrey', 11, 'Estadio Banorte', None, None),
    ('Pachuca', 'Necaxa', 11, 'Estadio Hidalgo', None, None),
    ('Atletico San Luis', 'Santos Laguna', 11, 'Estadio Alfonso Lastras', None, None),
    ('Pumas UNAM', 'Cruz Azul', 11, 'Estadio Olimpico Universitario', None, None),
    ('Necaxa', 'Atlas', 12, 'Estadio Victoria', None, None),
    ('Tijuana', 'Puebla', 12, 'Estadio Caliente', None, None),
    ('Atlante', 'Pumas UNAM', 12, 'Estadio Banorte', None, None),
    ('Guadalajara', 'Tigres', 12, 'Estadio Akron', None, None),
    ('Santos Laguna', 'Queretaro', 12, 'Estadio TSM Corona', None, None),
    ('Leon', 'America', 12, 'Estadio Nou Camp', None, None),
    ('Toluca', 'Atletico San Luis', 12, 'Estadio Nemesio Diez', None, None),
    ('Cruz Azul', 'FC Juarez', 12, 'Estadio Banorte', None, None),
    ('Monterrey', 'Pachuca', 12, 'Estadio BBVA', None, None),
    ('FC Juarez', 'Atlante', 13, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atletico San Luis', 'Queretaro', 13, 'Estadio Alfonso Lastras', None, None),
    ('Tigres', 'Leon', 13, 'Estadio Universitario', None, None),
    ('Guadalajara', 'Necaxa', 13, 'Estadio Akron', None, None),
    ('Puebla', 'Monterrey', 13, 'Estadio Cuauhtemoc', None, None),
    ('Atlas', 'America', 13, 'Estadio Jalisco', None, None),
    ('Toluca', 'Tijuana', 13, 'Estadio Nemesio Diez', None, None),
    ('Pachuca', 'Cruz Azul', 13, 'Estadio Hidalgo', None, None),
    ('Santos Laguna', 'Pumas UNAM', 13, 'Estadio TSM Corona', None, None),
    ('Necaxa', 'FC Juarez', 14, 'Estadio Victoria', None, None),
    ('Atlante', 'Atletico San Luis', 14, 'Estadio Banorte', None, None),
    ('Leon', 'Toluca', 14, 'Estadio Nou Camp', None, None),
    ('Monterrey', 'Guadalajara', 14, 'Estadio BBVA', None, None),
    ('Pumas UNAM', 'Tigres', 14, 'Estadio Olimpico Universitario', None, None),
    ('Atlas', 'Puebla', 14, 'Estadio Jalisco', None, None),
    ('America', 'Pachuca', 14, 'Estadio Banorte', None, None),
    ('Queretaro', 'Cruz Azul', 14, 'Estadio Corregidora', None, None),
    ('Tijuana', 'Santos Laguna', 14, 'Estadio Caliente', None, None),
    ('FC Juarez', 'Queretaro', 15, 'Estadio Olimpico Benito Juarez', None, None),
    ('Atletico San Luis', 'Atlas', 15, 'Estadio Alfonso Lastras', None, None),
    ('Puebla', 'Pumas UNAM', 15, 'Estadio Cuauhtemoc', None, None),
    ('Pachuca', 'Tigres', 15, 'Estadio Hidalgo', None, None),
    ('Monterrey', 'Tijuana', 15, 'Estadio BBVA', None, None),
    ('Guadalajara', 'Atlante', 15, 'Estadio Akron', None, None),
    ('America', 'Toluca', 15, 'Estadio Banorte', None, None),
    ('Santos Laguna', 'Necaxa', 15, 'Estadio TSM Corona', None, None),
    ('Cruz Azul', 'Leon', 15, 'Estadio Banorte', None, None),
    ('Necaxa', 'Tijuana', 16, 'Estadio Victoria', None, None),
    ('Atletico San Luis', 'FC Juarez', 16, 'Estadio Alfonso Lastras', None, None),
    ('Atlante', 'Santos Laguna', 16, 'Estadio Banorte', None, None),
    ('Atlas', 'Pachuca', 16, 'Estadio Jalisco', None, None),
    ('Tigres', 'Cruz Azul', 16, 'Estadio Universitario', None, None),
    ('Toluca', 'Monterrey', 16, 'Estadio Nemesio Diez', None, None),
    ('Pumas UNAM', 'America', 16, 'Estadio Olimpico Universitario', None, None),
    ('Queretaro', 'Puebla', 16, 'Estadio Corregidora', None, None),
    ('Leon', 'Guadalajara', 16, 'Estadio Nou Camp', None, None),
    ('Puebla', 'Atletico San Luis', 17, 'Estadio Cuauhtemoc', None, None),
    ('FC Juarez', 'Atlas', 17, 'Estadio Olimpico Benito Juarez', None, None),
    ('Tijuana', 'Atlante', 17, 'Estadio Caliente', None, None),
    ('Santos Laguna', 'Leon', 17, 'Estadio TSM Corona', None, None),
    ('Pachuca', 'Toluca', 17, 'Estadio Hidalgo', None, None),
    ('Pumas UNAM', 'Monterrey', 17, 'Estadio Olimpico Universitario', None, None),
    ('Tigres', 'America', 17, 'Estadio Universitario', None, None),
    ('Guadalajara', 'Cruz Azul', 17, 'Estadio Akron', None, None),
    ('Queretaro', 'Necaxa', 17, 'Estadio Corregidora', None, None),
]

# ─────────────────────────────────────────────────────────────────────────
# HORARIOS_PARTIDO — igual estructura que usaste en el Mundial.
# Formato "YYYY-MM-DD HH:MM", tiempo del centro de México.
# ─────────────────────────────────────────────────────────────────────────
HORARIOS_PARTIDO = {
    ('Necaxa', 'Atlante'): '2026-07-16 19:00',
    ('Tijuana', 'Tigres'): '2026-07-16 21:10',
    ('Atletico San Luis', 'Cruz Azul'): '2026-07-17 19:00',
    ('Leon', 'Atlas'): '2026-07-17 19:00',
    ('FC Juarez', 'Puebla'): '2026-07-17 21:00',
    ('Pumas UNAM', 'Pachuca'): '2026-07-18 17:00',
    ('Guadalajara', 'Toluca'): '2026-07-18 18:07',
    ('Monterrey', 'Santos Laguna'): '2026-07-18 19:00',
    ('Queretaro', 'America'): '2026-07-18 21:00',
    ('Cruz Azul', 'Puebla'): '2026-07-21 18:00',
    ('Toluca', 'Pumas UNAM'): '2026-07-21 21:00',
    ('Tigres', 'Atletico San Luis'): '2026-07-24 19:00',
    ('Tijuana', 'Leon'): '2026-07-24 20:00',
    ('Atlante', 'America'): '2026-07-24 20:00',
    ('Guadalajara', 'FC Juarez'): '2026-07-25 17:00',
    ('Santos Laguna', 'Atlas'): '2026-07-25 20:00',
    ('Necaxa', 'Monterrey'): '2026-07-26 17:00',
    ('Pachuca', 'Queretaro'): '2026-07-26 18:00',
    ('Puebla', 'Guadalajara'): '2026-07-31 19:00',
    ('FC Juarez', 'Pumas UNAM'): '2026-07-31 20:00',
    ('Atletico San Luis', 'Tijuana'): '2026-07-31 21:00',
    ('Queretaro', 'Tigres'): '2026-08-01 17:00',
    ('Atlas', 'Monterrey'): '2026-08-01 18:00',
    ('Leon', 'Pachuca'): '2026-08-01 18:00',
    ('Cruz Azul', 'Atlante'): '2026-08-01 20:00',
    ('America', 'Santos Laguna'): '2026-08-02 16:00',
    ('Toluca', 'Necaxa'): '2026-08-02 18:00',
    ('Atlante', 'Toluca'): '2026-08-15 17:00',
    ('Monterrey', 'FC Juarez'): '2026-08-15 19:00',
    ('Atlas', 'Tigres'): '2026-08-15 20:00',
    ('Pumas UNAM', 'Queretaro'): '2026-08-16 11:00',
    ('America', 'Atletico San Luis'): '2026-08-16 16:00',
    ('Santos Laguna', 'Guadalajara'): '2026-08-16 19:00',
    ('Tijuana', 'Cruz Azul'): '2026-08-16 20:00',
    ('Necaxa', 'Leon'): '2026-08-17 18:00',
    ('Pachuca', 'Puebla'): '2026-08-17 21:00',
    ('Puebla', 'Santos Laguna'): '2026-08-21 18:00',
    ('FC Juarez', 'America'): '2026-08-21 20:00',
    ('Guadalajara', 'Tijuana'): '2026-08-22 16:07',
    ('Queretaro', 'Toluca'): '2026-08-22 17:00',
    ('Leon', 'Monterrey'): '2026-08-22 19:00',
    ('Tigres', 'Atlante'): '2026-08-22 20:00',
    ('Cruz Azul', 'Atlas'): '2026-08-22 20:00',
    ('Pumas UNAM', 'Necaxa'): '2026-08-23 19:00',
    ('Atlante', 'Leon'): '2026-08-28 18:00',
    ('Necaxa', 'Cruz Azul'): '2026-08-28 18:00',
    ('Tijuana', 'Pumas UNAM'): '2026-08-28 21:00',
    ('Pachuca', 'Guadalajara'): '2026-08-29 16:00',
    ('Atlas', 'Queretaro'): '2026-08-29 17:00',
    ('America', 'Puebla'): '2026-08-29 19:00',
    ('Santos Laguna', 'Tigres'): '2026-08-29 20:00',
    ('Toluca', 'FC Juarez'): '2026-08-30 17:00',
    ('Monterrey', 'Atletico San Luis'): '2026-08-30 19:00',
    ('Puebla', 'Toluca'): '2026-09-04 19:00',
    ('FC Juarez', 'Pachuca'): '2026-09-04 21:00',
    ('Atletico San Luis', 'Guadalajara'): '2026-09-05 16:00',
    ('Queretaro', 'Monterrey'): '2026-09-05 16:00',
    ('Tigres', 'Necaxa'): '2026-09-05 18:00',
    ('America', 'Tijuana'): '2026-09-05 18:00',
    ('Atlas', 'Atlante'): '2026-09-05 21:00',
    ('Pumas UNAM', 'Leon'): '2026-09-06 11:00',
    ('Cruz Azul', 'Santos Laguna'): '2026-09-06 19:00',
    ('Necaxa', 'Puebla'): '2026-09-11 19:00',
    ('Atlante', 'Pachuca'): '2026-09-11 20:00',
    ('Tijuana', 'Queretaro'): '2026-09-11 21:00',
    ('Cruz Azul', 'America'): '2026-09-11 23:00',
    ('Toluca', 'Atlas'): '2026-09-12 00:00',
    ('Leon', 'Atletico San Luis'): '2026-09-12 16:00',
    ('Santos Laguna', 'FC Juarez'): '2026-09-13 17:00',
    ('Guadalajara', 'Pumas UNAM'): '2026-09-13 18:00',
    ('Monterrey', 'Tigres'): '2026-09-13 20:00',
    ('Puebla', 'Atlante'): '2026-09-18 18:00',
    ('FC Juarez', 'Tigres'): '2026-09-18 20:00',
    ('Atletico San Luis', 'Necaxa'): '2026-09-19 16:00',
    ('Atlas', 'Pumas UNAM'): '2026-09-19 17:00',
    ('Monterrey', 'Cruz Azul'): '2026-09-19 19:00',
    ('America', 'Guadalajara'): '2026-09-19 21:00',
    ('Toluca', 'Santos Laguna'): '2026-09-20 17:00',
    ('Pachuca', 'Tijuana'): '2026-09-20 17:00',
    ('Queretaro', 'Leon'): '2026-09-20 19:00',
    ('Atlante', 'Monterrey'): '2026-09-25 18:00',
    ('Tijuana', 'Atlas'): '2026-09-25 21:00',
    ('Guadalajara', 'Queretaro'): '2026-09-26 16:07',
    ('Santos Laguna', 'Pachuca'): '2026-09-26 18:00',
    ('Tigres', 'Puebla'): '2026-09-26 18:00',
    ('Cruz Azul', 'Toluca'): '2026-09-26 20:00',
    ('Pumas UNAM', 'Atletico San Luis'): '2026-09-27 11:00',
    ('Leon', 'FC Juarez'): '2026-09-27 19:00',
    ('Necaxa', 'America'): '2026-09-27 20:00',
    ('Queretaro', 'Atlante'): '2026-10-09 18:00',
    ('Puebla', 'Leon'): '2026-10-09 19:00',
    ('Tigres', 'Toluca'): '2026-10-09 21:00',
    ('FC Juarez', 'Tijuana'): '2026-10-10 17:00',
    ('Atlas', 'Guadalajara'): '2026-10-10 19:00',
    ('America', 'Monterrey'): '2026-10-10 20:00',
    ('Pachuca', 'Necaxa'): '2026-10-11 16:00',
    ('Atletico San Luis', 'Santos Laguna'): '2026-10-11 16:00',
    ('Pumas UNAM', 'Cruz Azul'): '2026-10-11 19:00',
    ('Necaxa', 'Atlas'): '2026-10-16 18:00',
    ('Tijuana', 'Puebla'): '2026-10-16 21:00',
    ('Atlante', 'Pumas UNAM'): '2026-10-16 21:00',
    ('Guadalajara', 'Tigres'): '2026-10-17 16:07',
    ('Santos Laguna', 'Queretaro'): '2026-10-17 17:00',
    ('Leon', 'America'): '2026-10-17 19:00',
    ('Toluca', 'Atletico San Luis'): '2026-10-17 19:00',
    ('Cruz Azul', 'FC Juarez'): '2026-10-17 20:00',
    ('Monterrey', 'Pachuca'): '2026-10-18 18:00',
    ('FC Juarez', 'Atlante'): '2026-10-20 18:00',
    ('Atletico San Luis', 'Queretaro'): '2026-10-20 18:00',
    ('Tigres', 'Leon'): '2026-10-20 20:00',
    ('Guadalajara', 'Necaxa'): '2026-10-20 20:07',
    ('Puebla', 'Monterrey'): '2026-10-21 18:00',
    ('Atlas', 'America'): '2026-10-21 18:00',
    ('Toluca', 'Tijuana'): '2026-10-21 18:00',
    ('Pachuca', 'Cruz Azul'): '2026-10-21 20:00',
    ('Santos Laguna', 'Pumas UNAM'): '2026-10-21 21:00',
    ('Necaxa', 'FC Juarez'): '2026-10-23 18:00',
    ('Atlante', 'Atletico San Luis'): '2026-10-23 20:00',
    ('Leon', 'Toluca'): '2026-10-24 17:00',
    ('Monterrey', 'Guadalajara'): '2026-10-24 19:00',
    ('Pumas UNAM', 'Tigres'): '2026-10-24 21:00',
    ('Atlas', 'Puebla'): '2026-10-25 17:00',
    ('America', 'Pachuca'): '2026-10-25 17:00',
    ('Queretaro', 'Cruz Azul'): '2026-10-25 19:00',
    ('Tijuana', 'Santos Laguna'): '2026-10-25 21:00',
    ('FC Juarez', 'Queretaro'): '2026-10-30 19:00',
    ('Atletico San Luis', 'Atlas'): '2026-10-30 19:00',
    ('Puebla', 'Pumas UNAM'): '2026-10-30 21:00',
    ('Pachuca', 'Tigres'): '2026-10-31 17:00',
    ('Monterrey', 'Tijuana'): '2026-10-31 19:00',
    ('Guadalajara', 'Atlante'): '2026-10-31 19:07',
    ('America', 'Toluca'): '2026-10-31 21:00',
    ('Santos Laguna', 'Necaxa'): '2026-11-01 17:00',
    ('Cruz Azul', 'Leon'): '2026-11-01 19:00',
    ('Necaxa', 'Tijuana'): '2026-11-06 19:00',
    ('Atletico San Luis', 'FC Juarez'): '2026-11-06 19:00',
    ('Atlante', 'Santos Laguna'): '2026-11-06 21:00',
    ('Atlas', 'Pachuca'): '2026-11-07 17:00',
    ('Tigres', 'Cruz Azul'): '2026-11-07 17:00',
    ('Toluca', 'Monterrey'): '2026-11-07 19:00',
    ('Pumas UNAM', 'America'): '2026-11-07 21:00',
    ('Queretaro', 'Puebla'): '2026-11-08 18:00',
    ('Leon', 'Guadalajara'): '2026-11-08 20:00',
    ('Puebla', 'Atletico San Luis'): '2026-11-20 19:00',
    ('FC Juarez', 'Atlas'): '2026-11-20 21:00',
    ('Tijuana', 'Atlante'): '2026-11-20 21:00',
    ('Santos Laguna', 'Leon'): '2026-11-21 17:00',
    ('Pachuca', 'Toluca'): '2026-11-21 17:00',
    ('Pumas UNAM', 'Monterrey'): '2026-11-21 19:00',
    ('Tigres', 'America'): '2026-11-21 21:00',
    ('Guadalajara', 'Cruz Azul'): '2026-11-22 17:07',
    ('Queretaro', 'Necaxa'): '2026-11-22 19:00',
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

# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE SIMULACIÓN
# ═══════════════════════════════════════════════════════════════════════
import numpy as np
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────
# ⚠️ FALTA — GOLES A FAVOR/CONTRA REALES POR EQUIPO (Clausura 2026)
# Igual que FORMA_MUNDIAL en tu predictor del Mundial. Sin esto,
# calcular_lambdas() deriva ataque/defensa de tu ELO (aproximación
# razonable pero menos precisa). En cuanto tengas los datos reales del
# Clausura 2026 (goles a favor, en contra, partidos jugados), llena este
# dict así: "Equipo": (goles_favor, goles_contra, partidos_jugados)
# ─────────────────────────────────────────────────────────────────────────
FORMA_LIGA_MX = {}

# ⚠️ FALTA — fechas en que cada equipo jugó Leagues Cup 2026 (4-13 agosto
# fase de grupos, luego eliminación directa si avanza). Pídele a
# Perplexity: "dame las fechas exactas de los partidos de Leagues Cup
# 2026 de los 18 equipos de Liga MX". Formato: "Equipo": ["YYYY-MM-DD", ...]
LEAGUES_CUP_FECHAS = {}

LIGA_PROMEDIO_GOLES = 1.35  # goles esperados por equipo en un partido "neutro"


def _fuerza_ataque_defensa(equipo):
    """
    Devuelve (factor_ataque, factor_defensa) para un equipo.
    factor_ataque > 1  -> anota más de lo normal
    factor_defensa > 1 -> concede MENOS de lo normal (ver uso en calcular_lambdas)
    Usa datos reales de FORMA_LIGA_MX si existen; si no, deriva un
    estimado a partir del ELO (menos preciso, pero funcional mientras
    consigues los goles reales del Clausura 2026).
    """
    forma = FORMA_LIGA_MX.get(equipo)
    if forma and forma[2] > 0:
        gf, gc, pj = forma
        ataque = (gf / pj) / LIGA_PROMEDIO_GOLES
        defensa = LIGA_PROMEDIO_GOLES / max(gc / pj, 0.2)
        return ataque, defensa

    # Fallback: derivar de ELO relativo al promedio de la liga
    elo = ELO.get(equipo, 1500)
    elo_prom = sum(ELO.values()) / len(ELO)
    diff = elo - elo_prom
    factor = diff / 400 * 0.35  # misma escala que usaste en el Mundial
    ataque = 1.0 + factor
    defensa = 1.0 + factor  # equipos de ELO alto también conceden menos
    return max(ataque, 0.5), max(defensa, 0.5)


def _partido_reciente_leagues_cup(equipo, fecha_partido_str, dias=7):
    """True si el equipo jugó Leagues Cup dentro de los `dias` previos
    a fecha_partido_str (formato 'YYYY-MM-DD')."""
    if not fecha_partido_str or equipo not in LEAGUES_CUP_FECHAS:
        return False
    try:
        fecha_partido = datetime.strptime(fecha_partido_str, "%Y-%m-%d")
    except ValueError:
        return False
    for f in LEAGUES_CUP_FECHAS[equipo]:
        f_dt = datetime.strptime(f, "%Y-%m-%d")
        if 0 <= (fecha_partido - f_dt).days <= dias:
            return True
    return False


def calcular_lambdas(local, visitante, arbitro=None, fecha_partido=None):
    """
    Calcula (lambda_local, lambda_visitante) — goles esperados de cada
    equipo — combinando:
      1. Ataque/Defensa (real si hay datos en FORMA_LIGA_MX, si no ELO)
      2. Altitud (bonus ofensivo al local en sedes altas, penalización
         al visitante no aclimatado)
      3. Árbitro (más tarjetas -> partido más trabado -> menos goles)
      4. Fatiga por Leagues Cup (-10% al ataque si jugó en los 7 días previos)
    """
    ataque_local, defensa_local = _fuerza_ataque_defensa(local)
    ataque_visit, defensa_visit = _fuerza_ataque_defensa(visitante)

    lam_local = LIGA_PROMEDIO_GOLES * ataque_local * defensa_visit
    lam_visit = LIGA_PROMEDIO_GOLES * ataque_visit * defensa_local
    # ventaja de local "base" (jugar en casa siempre ayuda un poco)
    lam_local *= 1.12

    # ── 1. Factor Altitud ──────────────────────────────────────────────
    alt_local = ALTITUD_EQUIPO.get(local)
    alt_sede_visitante = ALTITUD_EQUIPO.get(visitante)  # altitud de LA CIUDAD del visitante (para saber si está aclimatado)
    if alt_local and alt_local >= 1700:
        visitante_aclimatado = alt_sede_visitante is not None and alt_sede_visitante >= 1500
        if not visitante_aclimatado:
            # bonus escalado: a 2,680m (Toluca) el bonus es mayor que a 1,820m (Querétaro)
            bonus = min(0.30, max(0.10, (alt_local - 1200) / 1000 * 0.20))
            lam_local += bonus
            lam_visit *= 0.90  # el visitante rinde peor a falta de oxígeno

    # ── 2. Factor Arbitraje ──────────────────────────────────────────────
    if arbitro and arbitro in ARBITROS_LIGA_MX:
        prom_am_arbitro, _n = ARBITROS_LIGA_MX[arbitro]
        prom_liga = sum(v[0] for v in ARBITROS_LIGA_MX.values()) / len(ARBITROS_LIGA_MX)
        # un árbitro que saca más tarjetas de lo normal = partido más
        # cortado/físico = ligeramente menos gol; uno muy permisivo deja
        # fluir el juego = ligeramente más gol
        desviacion = (prom_am_arbitro - prom_liga) / prom_liga
        factor_arb = 1.0 - max(-0.10, min(0.15, desviacion * 0.30))
        lam_local *= factor_arb
        lam_visit *= factor_arb
    # si no conoces al árbitro, no se aplica ajuste (ARBITRO_DEFAULT ya
    # es razonable para el resto del padrón)

    # ── 3. Factor Fatiga (Leagues Cup) ──────────────────────────────────
    if _partido_reciente_leagues_cup(local, fecha_partido):
        lam_local *= 0.90
    if _partido_reciente_leagues_cup(visitante, fecha_partido):
        lam_visit *= 0.90

    return max(lam_local, 0.15), max(lam_visit, 0.15)


# ─────────────────────────────────────────────────────────────────────────
# TABLA GENERAL — puntos, GF/GC, diferencia de goles
# ─────────────────────────────────────────────────────────────────────────
def _tabla_vacia():
    return {equipo: {"Pts": 0, "PJ": 0, "G": 0, "E": 0, "P": 0,
                      "GF": 0, "GC": 0, "DG": 0} for equipo in EQUIPOS}


def _actualizar_tabla(tabla, local, visitante, gl, gv):
    tabla[local]["PJ"] += 1
    tabla[visitante]["PJ"] += 1
    tabla[local]["GF"] += gl
    tabla[local]["GC"] += gv
    tabla[visitante]["GF"] += gv
    tabla[visitante]["GC"] += gl
    if gl > gv:
        tabla[local]["Pts"] += 3
        tabla[local]["G"] += 1
        tabla[visitante]["P"] += 1
    elif gv > gl:
        tabla[visitante]["Pts"] += 3
        tabla[visitante]["G"] += 1
        tabla[local]["P"] += 1
    else:
        tabla[local]["Pts"] += 1
        tabla[visitante]["Pts"] += 1
        tabla[local]["E"] += 1
        tabla[visitante]["E"] += 1
    tabla[local]["DG"] = tabla[local]["GF"] - tabla[local]["GC"]
    tabla[visitante]["DG"] = tabla[visitante]["GF"] - tabla[visitante]["GC"]


def _clasificacion(tabla):
    """Ordena por Pts, luego diferencia de goles, luego goles a favor."""
    return sorted(tabla.items(),
                  key=lambda kv: (-kv[1]["Pts"], -kv[1]["DG"], -kv[1]["GF"]))


# ─────────────────────────────────────────────────────────────────────────
# LIGUILLA — cuartos/semis/final a ida y vuelta, reseeding tras cuartos
# (formato estándar Liga MX: 1v8, 2v7, 3v6, 4v5)
# ─────────────────────────────────────────────────────────────────────────
def _jugar_serie_ida_vuelta(mejor_seed, peor_seed, rng):
    """Ida: local el de peor posición. Vuelta: local el de mejor posición
    (ventaja de definir en casa, como en Liga MX). Si el marcador global
    queda empatado, se define por penales con probabilidad ligeramente
    inclinada según diferencia de ELO."""
    lam_a1, lam_b1 = calcular_lambdas(peor_seed, mejor_seed)
    g_ida_peor = rng.poisson(lam_a1)
    g_ida_mejor = rng.poisson(lam_b1)

    lam_a2, lam_b2 = calcular_lambdas(mejor_seed, peor_seed)
    g_vuelta_mejor = rng.poisson(lam_a2)
    g_vuelta_peor = rng.poisson(lam_b2)

    global_mejor = g_ida_mejor + g_vuelta_mejor
    global_peor = g_ida_peor + g_vuelta_peor

    if global_mejor > global_peor:
        return mejor_seed
    if global_peor > global_mejor:
        return peor_seed

    # empate global -> penales, ligera ventaja probabilística por ELO
    elo_mejor = ELO.get(mejor_seed, 1500)
    elo_peor = ELO.get(peor_seed, 1500)
    prob_mejor = 0.5 + max(-0.15, min(0.15, (elo_mejor - elo_peor) / 400 * 0.15))
    return mejor_seed if rng.random() < prob_mejor else peor_seed


def _simular_liguilla(top8_ordenado, rng):
    """top8_ordenado: lista de 8 equipos en orden de posición en la
    tabla general (1° a 8°). Devuelve el campeón."""
    cruces_cuartos = [
        (top8_ordenado[0], top8_ordenado[7]),
        (top8_ordenado[1], top8_ordenado[6]),
        (top8_ordenado[2], top8_ordenado[5]),
        (top8_ordenado[3], top8_ordenado[4]),
    ]
    semifinalistas = [_jugar_serie_ida_vuelta(a, b, rng) for a, b in cruces_cuartos]

    # reseeding: se reordenan según su posición original en la tabla
    semifinalistas.sort(key=lambda e: top8_ordenado.index(e))
    cruces_semis = [
        (semifinalistas[0], semifinalistas[3]),
        (semifinalistas[1], semifinalistas[2]),
    ]
    finalistas = [_jugar_serie_ida_vuelta(a, b, rng) for a, b in cruces_semis]
    finalistas.sort(key=lambda e: top8_ordenado.index(e))
    campeon = _jugar_serie_ida_vuelta(finalistas[0], finalistas[1], rng)
    return campeon


# ─────────────────────────────────────────────────────────────────────────
# SIMULACIÓN DE TEMPORADA COMPLETA (Monte Carlo)
# ─────────────────────────────────────────────────────────────────────────
def simular_temporada(n_temporadas=2000, semilla=None):
    """
    Corre `n_temporadas` simulaciones completas del Apertura 2026
    (fase regular + liguilla) y devuelve probabilidades agregadas.

    - Si un partido de PARTIDOS ya tiene resultado real (no None), se usa
      tal cual en vez de simularlo — así, conforme avance el torneo real,
      la simulación se vuelve cada vez más precisa (igual que en tu
      predictor del Mundial).
    - n_temporadas=2000-5000 ya da estimaciones estables. No hace falta
      llegar a millones como en una simulación de un solo partido: aquí
      cada "temporada" implica simular ~161 partidos (153 de fase regular
      + hasta 8 de liguilla), así que el costo computacional es mayor.
    """
    rng = np.random.default_rng(semilla)
    conteo_liguilla = {e: 0 for e in EQUIPOS}
    conteo_campeon = {e: 0 for e in EQUIPOS}
    suma_posicion = {e: 0 for e in EQUIPOS}
    ultima_tabla = None

    for _ in range(n_temporadas):
        tabla = _tabla_vacia()
        for local, visitante, jornada, estadio, resultado, arbitro in PARTIDOS:
            if resultado is not None:
                gl, gv = resultado
            else:
                fecha_str = HORARIOS_PARTIDO.get((local, visitante), "")
                fecha_str = fecha_str.split(" ")[0] if fecha_str else None
                lam_l, lam_v = calcular_lambdas(local, visitante, arbitro=arbitro,
                                                 fecha_partido=fecha_str)
                gl = int(rng.poisson(lam_l))
                gv = int(rng.poisson(lam_v))
            _actualizar_tabla(tabla, local, visitante, gl, gv)

        clasificacion = _clasificacion(tabla)
        for posicion, (equipo, _stats) in enumerate(clasificacion, start=1):
            suma_posicion[equipo] += posicion

        top8 = [equipo for equipo, _ in clasificacion[:8]]
        for equipo in top8:
            conteo_liguilla[equipo] += 1

        campeon = _simular_liguilla(top8, rng)
        conteo_campeon[campeon] += 1
        ultima_tabla = clasificacion

    prob_liguilla = {e: round(conteo_liguilla[e] / n_temporadas * 100, 1) for e in EQUIPOS}
    prob_campeon = {e: round(conteo_campeon[e] / n_temporadas * 100, 1) for e in EQUIPOS}
    posicion_promedio = {e: round(suma_posicion[e] / n_temporadas, 1) for e in EQUIPOS}

    return {
        "prob_liguilla": dict(sorted(prob_liguilla.items(), key=lambda kv: -kv[1])),
        "prob_campeon": dict(sorted(prob_campeon.items(), key=lambda kv: -kv[1])),
        "posicion_promedio": dict(sorted(posicion_promedio.items(), key=lambda kv: kv[1])),
        "ejemplo_tabla_final": ultima_tabla,  # última tabla simulada, solo de referencia
    }


if __name__ == "__main__":
    # Prueba rápida — corre pocas temporadas para verificar que todo
    # funciona antes de subirlo a Streamlit con un n_temporadas más alto.
    resultado = simular_temporada(n_temporadas=200, semilla=42)
    print("── Probabilidad de Liguilla (top 8) ──")
    for equipo, prob in resultado["prob_liguilla"].items():
        print(f"  {equipo:20s} {prob:5.1f}%")
    print("\n── Probabilidad de Campeón ──")
    for equipo, prob in list(resultado["prob_campeon"].items())[:8]:
        print(f"  {equipo:20s} {prob:5.1f}%")
