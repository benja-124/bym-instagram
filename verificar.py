#!/usr/bin/env python3
"""
Revisa calendario.json antes de que se publique nada.

Existe por un problema real: el 13 de septiembre salieron un reel y un carrusel
el mismo dia diciendo los mismos tres errores de inventario, y nadie se dio
cuenta hasta verlo en el perfil. Cuando la fila tiene cuarenta piezas escritas
en semanas distintas, la repeticion no se ve leyendo el archivo.

Que revisa:

  1. Separacion por tema. Cada pieza declara un 'tema'. Dos piezas del mismo
     tema tienen que estar separadas. Cuanto, depende del formato: los reels y
     carruseles son los que la gente ve, asi que entre ellos se exige mucho mas
     que cuando hay una foto de por medio.
  2. Choque el mismo dia. Dos piezas del mismo tema el mismo dia es el error
     que dio origen a esto, y no se salva con ninguna excusa.
  3. Titulos calcados. Dos piezas con el mismo titulo o la misma primera
     lamina, aunque el tema declarado sea distinto.
  4. Higiene: ids repetidos, temas sin declarar, carruseles fuera de rango.

Uso:
    python3 verificar.py             revisa todo el calendario
    python3 verificar.py --futuro    revisa solo lo que aun no se publica
    python3 verificar.py --estricto  solo los choques del mismo dia

Devuelve 1 si encuentra algo, para que la corrida de Actions salga en rojo.

Por que hay dos modos: la revision completa corre al cambiar el calendario y
sirve para que revises antes de que salga nada. La estricta corre justo antes
de publicar y solo mira el error que no tiene vuelta -- dos piezas del mismo
tema el mismo dia -- para que un aviso de separacion nunca deje la cuenta sin
publicar por su cuenta.
"""
import json
import pathlib
import sys
import unicodedata
from datetime import date

BASE = pathlib.Path(__file__).parent
CALENDARIO = BASE / "calendario.json"

# Dias minimos entre dos piezas del mismo tema.
#
# Un reel y un carrusel son las piezas que de verdad circulan, asi que dos del
# mismo tema muy juntas se leen como contenido repetido. Las fotos alcanzan
# mucho menos y Instagram las muestra a gente distinta, asi que se les exige
# menos: si no, un tema con cinco piezas obligaria a estirar la fila dos meses.
SEPARACION_FUERTE = 10   # reel o carrusel contra reel o carrusel
SEPARACION_SUAVE = 5     # cuando alguna de las dos es foto

PESADOS = {"reel", "carrusel"}


def separacion_exigida(a, b):
    return SEPARACION_FUERTE if (tipo(a) in PESADOS and tipo(b) in PESADOS) \
        else SEPARACION_SUAVE


def tipo(post):
    # Las entradas mas antiguas no traen 'tipo': eran todas fotos.
    return post.get("tipo") or "foto"


def dia(post):
    return date.fromisoformat(post["fecha"])


def titulo(post):
    """El titulo visible de la pieza, venga de donde venga."""
    if post.get("titulo"):
        return post["titulo"]
    laminas = post.get("laminas") or []
    if laminas and laminas[0].get("titulo"):
        return laminas[0]["titulo"]
    return ""


def normalizar(t):
    """Para comparar titulos sin que los acentos o las mayusculas estorben."""
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("<br>", " ")
    limpio = "".join(c if (c.isalnum() or c.isspace()) else " " for c in t)
    return limpio.split()


def revisar(calendario, estricto=False):
    problemas = []

    vistos = set()
    for p in calendario:
        if p["id"] in vistos:
            problemas.append(f"id repetido: {p['id']}")
        vistos.add(p["id"])
        # Una pieza sin tema es un descuido que hay que corregir, pero no es
        # razon para dejar la cuenta sin publicar: solo se avisa.
        if not p.get("tema") and not estricto:
            problemas.append(f"{p['id']} no declara 'tema'")
        if tipo(p) == "carrusel":
            n = len(p.get("partes") or p.get("laminas") or [])
            if not 2 <= n <= 10:
                problemas.append(
                    f"{p['id']} es carrusel y tiene {n} laminas (van de 2 a 10)")

    # Separacion y choques, tema por tema.
    por_tema = {}
    for p in calendario:
        por_tema.setdefault(p.get("tema"), []).append(p)

    for tema, piezas in sorted(por_tema.items()):
        if not tema:
            continue
        piezas = sorted(piezas, key=dia)
        for i, a in enumerate(piezas):
            for b in piezas[i + 1:]:
                distancia = (dia(b) - dia(a)).days
                minimo = separacion_exigida(a, b)
                if distancia >= minimo:
                    break  # el resto esta aun mas lejos
                if distancia == 0:
                    problemas.append(
                        f"{a['id']} ({tipo(a)}) y {b['id']} ({tipo(b)}) salen "
                        f"el MISMO dia {a['fecha']} con el tema '{tema}'")
                elif not estricto:
                    problemas.append(
                        f"{a['id']} ({tipo(a)}, {a['fecha']}) y {b['id']} "
                        f"({tipo(b)}, {b['fecha']}) comparten el tema '{tema}' "
                        f"y estan a {distancia} dia(s); el minimo es {minimo}")

    if estricto:
        return problemas

    # Titulos calcados, sin importar el tema declarado.
    por_titulo = {}
    for p in calendario:
        t = tuple(normalizar(titulo(p)))
        if len(t) >= 3:  # titulos de una o dos palabras se repiten sin problema
            por_titulo.setdefault(t, []).append(p)
    for t, piezas in por_titulo.items():
        if len(piezas) > 1:
            cuales = ", ".join(f"{p['id']} ({p['fecha']})" for p in piezas)
            problemas.append(f"titulo calcado \"{' '.join(t)}\" en: {cuales}")

    return problemas


def main():
    calendario = json.loads(CALENDARIO.read_text(encoding="utf-8"))

    estricto = "--estricto" in sys.argv

    if "--futuro" in sys.argv or estricto:
        calendario = [p for p in calendario if not p.get("publicado")]

    problemas = revisar(calendario, estricto=estricto)

    if not problemas:
        print(f"Calendario sin repeticiones ({len(calendario)} piezas "
              f"revisadas).")
        return 0

    print(f"{len(problemas)} problema(s) en el calendario:\n")
    for p in problemas:
        print(f"  - {p}")
    print("\nCorrige las fechas o el tema antes de que esto se publique.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
