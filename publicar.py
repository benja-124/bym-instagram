#!/usr/bin/env python3
"""
Publica en Instagram el post que corresponda a hoy, segun calendario.json.

Flujo de la API (Instagram API con inicio de sesion de Instagram):
  1. Se crea un "contenedor" con la URL publica de la imagen y el texto.
  2. Se espera a que Instagram procese ese contenedor.
  3. Se publica el contenedor.

Variables de entorno necesarias:
  IG_TOKEN    token de acceso (secreto de GitHub)
  IG_USER_ID  identificador de la cuenta de Instagram
  BASE_URL    URL publica donde viven las imagenes (GitHub Pages)
"""
import json
import os
import pathlib
import sys
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
    faltan = [n for n, v in (("IG_TOKEN", TOKEN), ("IG_USER_ID", USER_ID),
                             ("BASE_URL", BASE_URL)) if not v]
    return faltan


def llamar(metodo, ruta, params):
    """Llama a la API. Nunca imprime el token en los errores."""
    params = dict(params, access_token=TOKEN)
    url = f"{API}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        datos = None
    peticion = urllib.request.Request(url, data=datos, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors="replace")
        # Por si la API devolviera el token en el eco del error.
        cuerpo = cuerpo.replace(TOKEN, "[TOKEN OCULTO]") if TOKEN else cuerpo
        raise SystemExit(f"Error {e.code} en {ruta}: {cuerpo}")


def crear_contenedor(url_imagen, texto):
    print(f"  creando contenedor para {url_imagen}")
    r = llamar("POST", f"{USER_ID}/media",
               {"image_url": url_imagen, "caption": texto})
    return r["id"]


def esperar_procesado(id_contenedor, intentos=20, espera=5):
    """Instagram tarda unos segundos en procesar la imagen."""
    for i in range(intentos):
        r = llamar("GET", id_contenedor, {"fields": "status_code,status"})
        estado = r.get("status_code")
        if estado == "FINISHED":
            return True
        if estado == "ERROR":
            raise SystemExit(f"  Instagram rechazo la imagen: {r.get('status')}")
        print(f"  procesando... ({estado}, intento {i + 1})")
        time.sleep(espera)
    raise SystemExit("  el contenedor no termino de procesarse a tiempo")


def publicar(id_contenedor):
    r = llamar("POST", f"{USER_ID}/media_publish",
               {"creation_id": id_contenedor})
    return r["id"]


def main():
    faltan = faltan_variables()
    if faltan:
        raise SystemExit(f"Faltan variables de entorno: {', '.join(faltan)}")

    calendario = json.loads(CALENDARIO.read_text(encoding="utf-8"))
    hoy = date.today().isoformat()

    pendientes = [p for p in calendario
                  if p.get("fecha") == hoy and not p.get("publicado")]

    if not pendientes:
        print(f"No hay nada programado para hoy ({hoy}). Nada que hacer.")
        return

    # Publica de a uno por ejecucion, aunque haya varios programados el mismo dia.
    post = pendientes[0]
    print(f"Publicando {post['id']} ({hoy})")

    url_imagen = f"{BASE_URL}/imagenes/{post['id']}.png"
    contenedor = crear_contenedor(url_imagen, post["texto"])
    esperar_procesado(contenedor)
    id_publicacion = publicar(contenedor)

    print(f"  publicado. id: {id_publicacion}")

    # Marca como publicado para que no se repita.
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
