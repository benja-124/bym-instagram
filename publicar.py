#!/usr/bin/env python3
"""
Publica en Instagram lo que corresponda segun calendario.json.

Soporta tres tipos:
  foto      una imagen de imagenes/
  carrusel  2 a 10 imagenes en una sola publicacion
  reel      un video vertical de medios/

Flujo de la API (crear "contenedor" -> esperar proceso -> publicar).
Los videos tardan bastante mas que las imagenes en procesarse.

Variables de entorno:
  IG_TOKEN    token de acceso (secreto de GitHub)
  IG_USER_ID  identificador de la cuenta de Instagram
  BASE_URL    URL publica donde viven los archivos (GitHub Pages)
"""
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://graph.instagram.com/v23.0"
BASE = pathlib.Path(__file__).parent
CALENDARIO = BASE / "calendario.json"
CHILE = ZoneInfo("America/Santiago")

# Cuantas piezas puede publicar una sola corrida. Es 2 para que, si se salta
# una corrida (GitHub atrasa o descarta los procesos programados cuando esta
# cargado), la siguiente se ponga al dia en vez de arrastrar el atraso para
# siempre. El tope evita que un fin de semana caido vacie la fila de golpe.
MAX_POR_CORRIDA = 2


def momento(post):
    """Fecha y hora programadas de una pieza, en hora de Chile.

    Sin 'hora' se asume medianoche, que es como se comportaba antes: la pieza
    queda disponible apenas llega su fecha.
    """
    hora = post.get("hora") or "00:00"
    return datetime.fromisoformat(f"{post['fecha']}T{hora}").replace(tzinfo=CHILE)

TOKEN = os.environ.get("IG_TOKEN", "").strip()
USER_ID = os.environ.get("IG_USER_ID", "").strip()
BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")


def faltan_variables():
    return [n for n, v in (("IG_TOKEN", TOKEN), ("IG_USER_ID", USER_ID),
                           ("BASE_URL", BASE_URL)) if not v]


def llamar(metodo, ruta, params):
    """Llama a la API. Nunca deja el token visible en los errores."""
    params = dict(params, access_token=TOKEN)
    url = f"{API}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        datos = None
    peticion = urllib.request.Request(url, data=datos, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors="replace")
        cuerpo = cuerpo.replace(TOKEN, "[TOKEN OCULTO]") if TOKEN else cuerpo
        raise SystemExit(f"Error {e.code} en {ruta}: {cuerpo}")


def esperar(id_contenedor, intentos=40, espera=6):
    """Espera a que Instagram termine de procesar. Los videos tardan mas."""
    for i in range(intentos):
        r = llamar("GET", id_contenedor, {"fields": "status_code,status"})
        estado = r.get("status_code")
        if estado == "FINISHED":
            return
        if estado == "ERROR":
            raise SystemExit(f"  Instagram rechazo el archivo: {r.get('status')}")
        print(f"  procesando... ({estado}, intento {i + 1})")
        time.sleep(espera)
    raise SystemExit("  el contenedor no termino de procesarse a tiempo")


def extras(post):
    """Parametros opcionales comunes a foto, carrusel y reel."""
    d = {}
    if post.get("ubicacion"):
        d["location_id"] = post["ubicacion"]
    return d


def contenedor_foto(post):
    url = f"{BASE_URL}/imagenes/{post['id']}.png"
    print(f"  imagen: {url}")
    p = {"image_url": url, "caption": post["texto"], **extras(post)}
    if post.get("alt"):
        p["alt_text"] = post["alt"]
    return llamar("POST", f"{USER_ID}/media", p)["id"]


def contenedor_carrusel(post):
    # "partes" manda si esta; si no, se deducen de las laminas escritas
    # en el calendario, para no tener la lista de ids dos veces.
    partes = post.get("partes") or [l["id"] for l in post.get("laminas", [])]
    if not 2 <= len(partes) <= 10:
        raise SystemExit(
            f"Un carrusel lleva de 2 a 10 laminas ({post['id']}: {len(partes)})")
    hijos = []
    for parte in partes:
        url = f"{BASE_URL}/imagenes/{parte}.png"
        print(f"  parte: {url}")
        r = llamar("POST", f"{USER_ID}/media",
                   {"image_url": url, "is_carousel_item": "true"})
        hijos.append(r["id"])
    for h in hijos:
        esperar(h, intentos=15, espera=3)
    p = {"media_type": "CAROUSEL", "children": ",".join(hijos),
         "caption": post["texto"], **extras(post)}
    return llamar("POST", f"{USER_ID}/media", p)["id"]


def contenedor_reel(post):
    url = f"{BASE_URL}/medios/{post['id']}.mp4"
    print(f"  video: {url}")
    p = {"media_type": "REELS", "video_url": url,
         "caption": post["texto"], **extras(post)}
    if post.get("portada"):
        p["cover_url"] = f"{BASE_URL}/imagenes/{post['portada']}.png"
    return llamar("POST", f"{USER_ID}/media", p)["id"]


CONSTRUCTORES = {
    "foto": contenedor_foto,
    "carrusel": contenedor_carrusel,
    "reel": contenedor_reel,
}


def main():
    faltan = faltan_variables()
    if faltan:
        raise SystemExit(f"Faltan variables de entorno: {', '.join(faltan)}")

    calendario = json.loads(CALENDARIO.read_text(encoding="utf-8"))
    ahora = datetime.now(CHILE)

    # El calendario es una fila de espera: se toman las piezas sin publicar
    # cuya fecha y hora ya pasaron, de la mas antigua a la mas nueva.
    pendientes = sorted(
        (p for p in calendario if not p.get("publicado") and momento(p) <= ahora),
        key=momento)

    if not pendientes:
        print(f"No hay pendientes para {ahora:%Y-%m-%d %H:%M} (hora de Chile).")
        return

    toca = pendientes[:MAX_POR_CORRIDA]
    if len(pendientes) > len(toca):
        print(f"Hay {len(pendientes)} pendientes; publico {len(toca)} y el resto "
              f"queda para la proxima corrida.")

    publicados = 0
    for post in toca:
        tipo = post.get("tipo", "foto")
        if tipo not in CONSTRUCTORES:
            raise SystemExit(f"Tipo desconocido en {post['id']}: {tipo}")

        programado = momento(post)
        atraso = "" if programado.date() == ahora.date() else \
            f" (atrasado desde {programado:%d-%m %H:%M})"
        print(f"Publicando {post['id']} [{tipo}]{atraso}.")

        contenedor = CONSTRUCTORES[tipo](post)
        esperar(contenedor)
        id_publicacion = llamar("POST", f"{USER_ID}/media_publish",
                                {"creation_id": contenedor})["id"]
        print(f"  publicado. id: {id_publicacion}")

        for p in calendario:
            if p["id"] == post["id"]:
                p["publicado"] = True
                p["id_publicacion"] = id_publicacion

        # Se guarda despues de cada pieza: si la segunda falla, la primera no
        # se vuelve a publicar en la corrida siguiente.
        CALENDARIO.write_text(
            json.dumps(calendario, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        publicados += 1

    print(f"calendario.json actualizado ({publicados} publicada(s)).")


if __name__ == "__main__":
    main()
