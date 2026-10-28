"""
liga_mx_arbitros_fmf.py — carga los árbitros centrales de la siguiente
jornada desde la página de designaciones de la Comisión de Árbitros FMF:

    https://arbitraje.fmf.mx/designacion-arbitral_2026-2027_liga-mx_apertura_jornada-N

La página arma la tabla con JavaScript, así que se abre con Playwright
(Chromium headless) y se lee el texto ya renderizado. No se conoce un
endpoint JSON público, por eso el parseo es por texto: para cada partido
de la jornada en PARTIDOS se busca el bloque más chico de la página que
mencione a los dos equipos, y dentro de él el árbitro central.

Solo llena árbitros que hoy están en None (nunca pisa uno ya cargado,
salvo --forzar). Un árbitro que no esté en ARBITROS_LIGA_MX se agrega con
el placeholder (4.5, 0.15) = ARBITRO_DEFAULT y un comentario de debut,
igual que cuando se carga a mano (ver CLAUDE.md).

Uso:
    python liga_mx_arbitros_fmf.py                 # jornadas pendientes, escribe el skeleton
    python liga_mx_arbitros_fmf.py --jornada 15    # una jornada específica
    python liga_mx_arbitros_fmf.py --dry-run       # solo muestra lo que cargaría
    python liga_mx_arbitros_fmf.py --debug-dir d/  # guarda el texto renderizado y las respuestas JSON

Lo corre .github/workflows/arbitros_fmf.yml, que sube el cambio directo a
main (los datos de partidos no pasan por PR).
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from liga_mx_predictor_skeleton import (
    ARBITROS_LIGA_MX,
    ARBITROS_LIGA_MX_TRANSFERMARKT,
    EQUIPOS,
    PARTIDOS,
)

SKELETON = Path(__file__).with_name("liga_mx_predictor_skeleton.py")
URL_DESIGNACION = (
    "https://arbitraje.fmf.mx/designacion-arbitral_2026-2027_liga-mx_apertura_jornada-{jornada}"
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

# Palabras clave (ya sin acentos y en minúsculas) con las que la FMF nombra
# a cada club. Confirmado contra la noticia de designaciones de la J11
# (arbitraje.fmf.mx/detalle-noticia?id=2312): "Puebla F.C.", "Tigres de la
# U.A.N.L.", "FC Juárez", "Club Tijuana", "Gallos Blancos de Querétaro",
# "Rayados de Monterrey", "Club Atlético de San Luis", "Universidad
# Nacional", etc. El orden importa: "atlas" va con límite de palabra para
# no confundirse con "atlante" ni "atletico".
PALABRAS_EQUIPO = [
    ("Atletico San Luis", r"\bsan luis\b"),
    ("Pumas UNAM", r"\buniversidad nacional\b|\bpumas\b|\bunam\b"),
    ("Tigres", r"\btigres\b|\bu\.?a\.?n\.?l\b"),
    ("Monterrey", r"\bmonterrey\b|\brayados\b"),
    ("Queretaro", r"\bqueretaro\b|\bgallos blancos\b"),
    ("FC Juarez", r"\bjuarez\b"),
    ("Tijuana", r"\btijuana\b|\bxolos\b"),
    ("Puebla", r"\bpuebla\b"),
    ("America", r"\bamerica\b"),
    ("Toluca", r"\btoluca\b"),
    ("Leon", r"\bleon\b"),
    ("Atlante", r"\batlante\b"),
    ("Atlas", r"\batlas\b"),
    ("Guadalajara", r"\bguadalajara\b|\bchivas\b"),
    ("Santos Laguna", r"\bsantos\b"),
    ("Pachuca", r"\bpachuca\b"),
    ("Necaxa", r"\bnecaxa\b"),
    ("Cruz Azul", r"\bcruz azul\b"),
]
_REGEX_EQUIPO = [(eq, re.compile(p)) for eq, p in PALABRAS_EQUIPO]

# Etiquetas que marcan el inicio de los demás oficiales: un nombre que
# aparece después de una de ellas ya no es el central.
_ETIQUETAS_OTROS = re.compile(r"asistente|cuarto|4to|var\b|avar|observador|asesor")
_ETIQUETA_CENTRAL = re.compile(r"central|arbitro\b")
_NO_ES_NOMBRE = re.compile(
    r"estadio|arena|jornada|designaci|liga|apertura|clausura|fecha|hora|"
    r"comision|arbitr|local|visit|partido|sede|\d"
)


def quitar_acentos(texto: str) -> str:
    """Quita acentos pero conserva la ñ (convención: "Lopez Peñuelas")."""
    texto = texto.replace("ñ", "\0n").replace("Ñ", "\0N")
    sin = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin.replace("\0n", "ñ").replace("\0N", "Ñ")


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", quitar_acentos(texto)).strip().lower()


def equipos_en_texto(texto: str) -> list:
    """Equipos internos (EQUIPOS) mencionados en un texto, en orden de aparición."""
    norm = _normalizar(texto)
    encontrados = []
    for equipo, regex in _REGEX_EQUIPO:
        m = regex.search(norm)
        if m:
            encontrados.append((m.start(), equipo))
    return [eq for _, eq in sorted(encontrados)]


def emparejar_equipo_fmf(nombre: str):
    """Nombre FMF de un club -> nombre interno, o None si no hay match exacto de uno."""
    eqs = equipos_en_texto(nombre)
    return eqs[0] if len(eqs) == 1 else None


def arbitros_conocidos() -> dict:
    """Nombre normalizado -> nombre interno, de todas las fuentes del skeleton."""
    nombres = set(ARBITROS_LIGA_MX) | set(ARBITROS_LIGA_MX_TRANSFERMARKT)
    nombres |= {p[5] for p in PARTIDOS if p[5]}
    return {_normalizar(n): n for n in nombres}


def _parece_nombre(token: str) -> bool:
    norm = _normalizar(token)
    if _NO_ES_NOMBRE.search(norm) or equipos_en_texto(token):
        return False
    palabras = norm.split()
    return 2 <= len(palabras) <= 6 and all(re.fullmatch(r"[a-zñ.'-]+", p) for p in palabras)


def _formatear_nombre(token: str) -> str:
    palabras = quitar_acentos(token).split()
    minus = {"de", "del", "la", "las", "los", "y"}
    return " ".join(
        p.lower() if (p.lower() in minus and i > 0) else p[:1].upper() + p[1:].lower()
        for i, p in enumerate(palabras)
    )


def arbitro_central_en_bloque(bloque: str, conocidos: dict):
    """
    Del texto de un partido (fila de tabla o tarjeta), saca el árbitro
    central. Se parte en celdas/líneas; el central es el primer nombre de
    persona antes de cualquier etiqueta de asistente/cuarto/VAR (la FMF
    lista al central primero). Si hay una etiqueta "Central", se toma el
    nombre que la sigue. Devuelve (nombre, es_conocido) o (None, False).
    """
    tokens = [t.strip() for t in re.split(r"[\t\n|]+", bloque) if t.strip()]
    candidatos = []
    tras_central = False
    for tok in tokens:
        norm = _normalizar(tok)
        # "Árbitro central: Fulano" en una sola celda
        m = re.match(r"^(?:arbitro\s+)?central\s*:?\s*(.+)$", norm)
        if m and _parece_nombre(m.group(1)):
            return _resolver_nombre(tok.split(":", 1)[-1] if ":" in tok else tok, conocidos)
        if _ETIQUETAS_OTROS.search(norm) and not _parece_nombre(tok):
            if candidatos:
                break
            tras_central = False
            continue
        if _ETIQUETA_CENTRAL.search(norm) and not _parece_nombre(tok):
            tras_central = True
            continue
        if _parece_nombre(tok):
            if tras_central:
                return _resolver_nombre(tok, conocidos)
            candidatos.append(tok)

    # Sin etiquetas: el primer nombre conocido, y si no hay, el primer nombre.
    for tok in candidatos:
        if _normalizar(tok) in conocidos:
            return conocidos[_normalizar(tok)], True
    if candidatos:
        return _resolver_nombre(candidatos[0], conocidos)
    return None, False


def _resolver_nombre(token: str, conocidos: dict):
    norm = _normalizar(token)
    if norm in conocidos:
        return conocidos[norm], True
    return _formatear_nombre(token), False


def partidos_de_jornada(jornada: int) -> list:
    return [p for p in PARTIDOS if p[2] == jornada]


def jornadas_por_cargar() -> list:
    """
    Jornadas con partidos sin resultado y sin árbitro, posteriores a la
    última jornada con resultados (así se ignoran las rezagadas como la J7,
    cuyos árbitros se designan aparte).
    """
    jugadas = [p[2] for p in PARTIDOS if p[4] is not None]
    ultima = max(jugadas) if jugadas else 0
    pendientes = sorted({p[2] for p in PARTIDOS if p[4] is None and p[5] is None and p[2] > ultima})
    return pendientes[:2]


def leer_pagina(jornada: int, debug_dir=None) -> list:
    """Abre la página con Chromium y devuelve el innerText de cada elemento."""
    from playwright.sync_api import sync_playwright

    url = URL_DESIGNACION.format(jornada=jornada)
    respuestas_json = []
    respuestas_xhr = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # User agent de Chrome normal: el de headless ("HeadlessChrome")
        # lo bloquean algunos sitios.
        page = browser.new_page(locale="es-MX", user_agent=USER_AGENT)

        def _guardar(resp):
            tipo = resp.headers.get("content-type") or ""
            if resp.request.resource_type in ("xhr", "fetch"):
                respuestas_xhr.append(f"{resp.status} {tipo} {resp.url}")
            if "json" in tipo:
                try:
                    respuestas_json.append({"url": resp.url, "body": resp.json()})
                except Exception:
                    pass

        page.on("response", _guardar)
        resp = page.goto(url, wait_until="networkidle", timeout=90_000)
        # La tabla puede llegar después del networkidle: se espera hasta 30 s
        # a que el texto mencione al menos un club.
        try:
            page.wait_for_function(
                "() => /Toluca|Pachuca|Necaxa|Cruz Azul|Puebla/i.test(document.body.innerText)",
                timeout=30_000,
            )
        except Exception:
            pass
        textos = page.evaluate(
            "() => Array.from(document.body.querySelectorAll('*'))"
            ".map(e => e.innerText || '').filter(t => t.trim())"
        )
        if debug_dir:
            cuerpo = page.inner_text("body")
            print(f"  HTTP {resp.status if resp else '?'} · {page.url} · título: {page.title()!r}")
            print(f"  {len(respuestas_xhr)} respuestas XHR/fetch:")
            for r in respuestas_xhr[:30]:
                print(f"    {r}")
            print("  --- texto de la página (primeros 3000 caracteres) ---")
            print("  " + cuerpo[:3000].replace("\n", "\n  "))
            print("  --- fin ---")
            d = Path(debug_dir)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"jornada_{jornada}.txt").write_text(cuerpo, encoding="utf-8")
            (d / f"jornada_{jornada}.html").write_text(page.content(), encoding="utf-8")
            (d / f"jornada_{jornada}.json").write_text(
                json.dumps(respuestas_json, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8",
            )
        browser.close()
    # Si la página trae los datos en JSON, sus cadenas también sirven como
    # bloques (cada objeto aplanado a texto).
    for r in respuestas_json:
        textos.extend(_aplanar_json(r["body"]))
    return textos


def _aplanar_json(obj) -> list:
    bloques = []
    if isinstance(obj, dict):
        bloques.append("\n".join(str(v) for v in obj.values() if isinstance(v, (str, int, float))))
        for v in obj.values():
            bloques.extend(_aplanar_json(v))
    elif isinstance(obj, list):
        for v in obj:
            bloques.extend(_aplanar_json(v))
    return bloques


def extraer_arbitros(jornada: int, textos: list) -> dict:
    """
    {(local, visita): (arbitro, es_conocido)} para los partidos de la
    jornada que aparecen en la página. Para cada partido se usa el bloque
    de texto más corto que mencione exactamente a esos dos equipos y traiga
    un nombre de árbitro (el más corto a secas puede ser solo "Local vs
    Visita", sin los oficiales).
    """
    conocidos = arbitros_conocidos()
    bloques = {}
    for t in textos:
        eqs = equipos_en_texto(t)
        if len(eqs) == 2:
            bloques.setdefault(frozenset(eqs), set()).add(t)

    resultado = {}
    for local, visita, *_ in partidos_de_jornada(jornada):
        for bloque in sorted(bloques.get(frozenset((local, visita)), ()), key=len):
            nombre, conocido = arbitro_central_en_bloque(bloque, conocidos)
            if nombre:
                resultado[(local, visita)] = (nombre, conocido)
                break
    return resultado


def aplicar_al_skeleton(jornada: int, arbitros: dict, forzar: bool = False) -> list:
    """Escribe los árbitros en PARTIDOS (y altas nuevas en ARBITROS_LIGA_MX). Devuelve los cambios."""
    codigo = SKELETON.read_text(encoding="utf-8")
    cambios = []
    nuevos = []
    for (local, visita), (nombre, conocido) in arbitros.items():
        patron = re.compile(
            r"(\('%s', '%s', %d, '[^']*', (?:None|\(\d+, \d+\)), )(None|'[^']*')(\),)"
            % (re.escape(local), re.escape(visita), jornada)
        )
        m = patron.search(codigo)
        if not m:
            print(f"  ! no encontré la tupla de {local} vs {visita} en PARTIDOS")
            continue
        actual = m.group(2)
        if actual != "None" and not forzar:
            if actual.strip("'") != nombre:
                print(f"  ! {local} vs {visita}: ya tenía {actual}, la FMF dice {nombre} (no se cambia)")
            continue
        if actual.strip("'") == nombre:
            continue
        codigo = codigo[: m.start()] + m.group(1) + f"'{nombre}'" + m.group(3) + codigo[m.end():]
        cambios.append(f"{local} vs {visita}: {nombre}")
        if not conocido and nombre not in ARBITROS_LIGA_MX and nombre not in nuevos:
            nuevos.append((nombre, local, visita))

    for nombre, local, visita in nuevos:
        alta = (
            f"    # NUEVO — debuta en Liga MX (para efectos de este modelo) dirigiendo\n"
            f"    # {local}-{visita} (J{jornada}), según la designación de la FMF. Sin\n"
            f"    # ficha con promedio confirmado: usa ARBITRO_DEFAULT como placeholder.\n"
            f"    \"{nombre}\": (4.5, 0.15),\n"
        )
        inicio = codigo.index("ARBITROS_LIGA_MX = {")
        cierre = codigo.index("\n}\n", inicio) + 1
        codigo = codigo[:cierre] + alta + codigo[cierre:]
        cambios.append(f"árbitro nuevo en ARBITROS_LIGA_MX: {nombre}")

    if cambios:
        SKELETON.write_text(codigo, encoding="utf-8")
    return cambios


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--jornada", type=int, action="append", help="jornada a cargar (repetible)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe el skeleton")
    ap.add_argument("--forzar", action="store_true", help="reemplaza árbitros ya cargados")
    ap.add_argument("--debug-dir", help="carpeta para guardar el texto renderizado")
    args = ap.parse_args()

    jornadas = args.jornada or jornadas_por_cargar()
    if not jornadas:
        print("No hay jornadas pendientes de árbitro.")
        return 0

    todos = []
    for j in jornadas:
        print(f"Jornada {j}: {URL_DESIGNACION.format(jornada=j)}")
        textos = leer_pagina(j, args.debug_dir)
        arbitros = extraer_arbitros(j, textos)
        total = len(partidos_de_jornada(j))
        print(f"  {len(arbitros)}/{total} partidos con árbitro en la página")
        for (l, v), (n, conocido) in arbitros.items():
            print(f"  {l} vs {v}: {n}{'' if conocido else '  (NUEVO)'}")
        if args.dry_run or not arbitros:
            continue
        todos += [f"J{j} {c}" for c in aplicar_al_skeleton(j, arbitros, args.forzar)]

    if todos:
        print("Cambios:\n  " + "\n  ".join(todos))
    else:
        print("Sin cambios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
