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
from datetime import date

API = "https://graph.instagram.com/v23.0"
BASE = pathlib.Path(__file__).parent
CALENDARIO = BASE / "calendario.json"

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
    hijos = []
    for parte in post["partes"]:
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
    hoy = date.today().isoformat()

    # El calendario es una fila de espera: se toma el mas antiguo sin publicar
    # cuya fecha ya llego. Si una corrida falla, la siguiente se pone al dia.
    pendientes = sorted(
        (p for p in calendario
         if not p.get("publicado") and p.get("fecha", "9999") <= hoy),
        key=lambda p: (p.get("fecha", ""), p.get("id", "")))

    if not pendientes:
        print(f"No hay pendientes con fecha hasta hoy ({hoy}).")
        return

    post = pendientes[0]
    tipo = post.get("tipo", "foto")
    if tipo not in CONSTRUCTORES:
        raise SystemExit(f"Tipo desconocido en {post['id']}: {tipo}")

    atraso = "" if post["fecha"] == hoy else f" (atrasado desde {post['fecha']})"
    print(f"Publicando {post['id']} [{tipo}]{atraso}. "
          f"Quedan {len(pendientes) - 1} en fila.")

    contenedor = CONSTRUCTORES[tipo](post)
    esperar(contenedor)
    id_publicacion = llamar("POST", f"{USER_ID}/media_publish",
                            {"creation_id": contenedor})["id"]
    print(f"  publicado. id: {id_publicacion}")

    for p in calendario:
        if p["id"] == post["id"]:
            p["publicado"] = True
            p["id_publicacion"] = id_publicacion
    CALENDARIO.write_text(
        json.dumps(calendario, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("  calendario.json actualizado")


if __name__ == "__main__":
    main()
