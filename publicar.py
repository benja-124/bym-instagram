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


def normalizar_texto(t):
    """Primera linea del caption, sin espacios de mas. Sirve de huella."""
    return " ".join((t or "").strip().split())[:120]


_publicado_ya = None


def publicadas_en_instagram():
    """Lo que la cuenta ya tiene publicado, segun la propia API.

    El calendario no es una fuente confiable de que salio y que no: basta
    que alguien suba por el navegador una version anterior del archivo para
    que una pieza ya publicada vuelva a figurar como pendiente. Paso de
    verdad el 13 de septiembre y 'reel-errores' salio dos veces.

    Por eso, antes de publicar, se le pregunta a Instagram.
    """
    global _publicado_ya
    if _publicado_ya is None:
        r = llamar("GET", f"{USER_ID}/media",
                   {"fields": "id,caption", "limit": "50"})
        _publicado_ya = {
            "ids": {m["id"] for m in r.get("data", [])},
            "textos": {normalizar_texto(m.get("caption"))
                       for m in r.get("data", [])},
        }
        print(f"  la cuenta ya tiene {len(_publicado_ya['ids'])} "
              f"publicaciones recientes")
    return _publicado_ya


def ya_salio(post):
    """True si esta pieza ya esta en el perfil, diga lo que diga el calendario."""
    hechas = publicadas_en_instagram()
    if post.get("id_publicacion") in hechas["ids"]:
        return True
    return normalizar_texto(post.get("texto")) in hechas["textos"]


def extras(post):
    """Parametros opcionales comunes a foto, carrusel y reel."""
    d = {}
    if post.get("ubicacion"):
        d["location_id"] = post["ubicacion"]
    return d


def describir(datos):
    """Texto alternativo a partir de lo que dice la propia grafica.

    Importa mas de lo que parece. Sin 'alt', Instagram inventa uno mirando la
    imagen, y lo que invento para estas graficas fue "may be a meme of bread",
    "crossword puzzle" y "doodle". Con eso clasifica el tema de la publicacion
    y decide a quien se la muestra, asi que conviene decirselo nosotros.
    """
    partes = [datos.get("kicker"), datos.get("titulo"), datos.get("bajada")]
    partes += datos.get("items") or []
    for paso in datos.get("pasos") or []:
        if len(paso) > 1:
            partes.append(paso[1])
    limpias = [p.replace("<br>", " ").strip().rstrip(".").strip()
               for p in partes if isinstance(p, str) and p.strip()]
    texto = ". ".join(p for p in limpias if p)
    return " ".join(texto.split())[:900]  # Instagram corta cerca de 1000


def contenedor_foto(post):
    url = f"{BASE_URL}/imagenes/{post['id']}.png"
    print(f"  imagen: {url}")
    p = {"image_url": url, "caption": post["texto"], **extras(post)}
    alt = post.get("alt") or describir(post)
    if alt:
        p["alt_text"] = alt
    return llamar("POST", f"{USER_ID}/media", p)["id"]


def contenedor_carrusel(post):
    # "partes" manda si esta; si no, se deducen de las laminas escritas
    # en el calendario, para no tener la lista de ids dos veces.
    laminas = {l["id"]: l for l in post.get("laminas", [])}
    partes = post.get("partes") or list(laminas)
    if not 2 <= len(partes) <= 10:
        raise SystemExit(
            f"Un carrusel lleva de 2 a 10 laminas ({post['id']}: {len(partes)})")
    hijos = []
    for parte in partes:
        url = f"{BASE_URL}/imagenes/{parte}.png"
        print(f"  parte: {url}")
        p = {"image_url": url, "is_carousel_item": "true"}
        # El alt va en cada lamina, no en el carrusel: es lo unico que
        # Instagram acepta por separado en cada una.
        alt = laminas.get(parte, {}).get("alt") or describir(laminas.get(parte, {}))
        if alt:
            p["alt_text"] = alt
        r = llamar("POST", f"{USER_ID}/media", p)
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

        # Antes de crear nada: preguntarle a Instagram si esto ya salio.
        if ya_salio(post):
            print(f"  YA ESTABA PUBLICADO. No se publica de nuevo; solo se "
                  f"corrige el calendario.")
            for p in calendario:
                if p["id"] == post["id"]:
                    p["publicado"] = True
            CALENDARIO.write_text(
                json.dumps(calendario, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            continue

        try:
            contenedor = CONSTRUCTORES[tipo](post)
        except SystemExit:
            # La ubicacion es lo unico opcional que puede tumbar la llamada
            # entera: si el location_id no existe o Instagram lo rechaza, la
            # peticion falla completa. Antes que perder la publicacion, se
            # reintenta sin ubicacion y se avisa.
            if not post.get("ubicacion"):
                raise
            print("  fallo con ubicacion; reintento sin ella. "
                  f"Revisa el location_id de {post['id']}.")
            sin_ubicacion = {k: v for k, v in post.items() if k != "ubicacion"}
            contenedor = CONSTRUCTORES[tipo](sin_ubicacion)
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
