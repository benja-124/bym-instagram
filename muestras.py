#!/usr/bin/env python3
"""
Genera muestras de voz para comparar motores antes de elegir uno.

Corre en GitHub Actions (ahi si hay red abierta). Deja los audios en
muestras/ junto a una pagina index.html con un reproductor por voz,
que se puede escuchar desde GitHub Pages.

Todos los motores probados aqui permiten uso comercial:
  Kokoro-82M   Apache 2.0
  Piper        MIT
  Chatterbox   MIT (lleva marca de agua inaudible de Resemble AI)
"""
import json
import pathlib
import subprocess
import sys
import traceback
import urllib.request

BASE = pathlib.Path(__file__).parent
OUT = BASE / "muestras"
TMP = BASE / "_voz"
OUT.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)

TEXTO = ("Con ByM Solutions tu inventario se descuenta solo. "
         "Te avisamos antes de que un producto se acabe, "
         "y el pedido al proveedor sale automaticamente.")

# Mismo texto con acentos para los motores que los manejan bien.
TEXTO_ACENTOS = ("Con ByM Solutions tu inventario se descuenta solo. "
                 "Te avisamos antes de que un producto se acabe, "
                 "y el pedido al proveedor sale automáticamente.")

hechas = []


def a_mp3(wav, nombre, motor, voz, nota):
    """Normaliza el volumen y guarda como mp3 para que pese poco."""
    destino = OUT / f"{nombre}.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100",
        "-c:a", "libmp3lame", "-b:a", "128k", str(destino)], check=True)
    hechas.append({"archivo": destino.name, "motor": motor,
                   "voz": voz, "nota": nota})
    print(f"  OK  {destino.name}")


def bajar(url, destino):
    if destino.exists() and destino.stat().st_size > 1000:
        return destino
    print(f"  bajando {url.rsplit('/', 1)[-1]}")
    urllib.request.urlretrieve(url, destino)
    return destino


# --------------------------------------------------------------- Kokoro
def kokoro():
    import soundfile as sf
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="e")          # 'e' = espanol
    for voz, nota in (("ef_dora", "Femenina"), ("em_alex", "Masculina")):
        trozos = [a for _, _, a in pipe(TEXTO_ACENTOS, voice=voz, speed=1.0)]
        if not trozos:
            print(f"  sin audio para {voz}")
            continue
        import numpy as np
        audio = np.concatenate(trozos)
        wav = TMP / f"kokoro-{voz}.wav"
        sf.write(wav, audio, 24000)
        a_mp3(wav, f"kokoro-{voz}", "Kokoro-82M", voz, nota)


# ---------------------------------------------------------------- Piper
VOCES_PIPER = [
    ("es_MX-claude-high", "es/es_MX/claude/high", "Femenina, mexicana"),
    ("es_MX-ald-medium", "es/es_MX/ald/medium", "Masculina, mexicana"),
    ("es_AR-daniela-high", "es/es_AR/daniela/high", "Femenina, argentina"),
    ("es_ES-davefx-medium", "es/es_ES/davefx/medium", "Masculina, de Espana"),
]
RAIZ_PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def piper():
    for nombre, ruta, nota in VOCES_PIPER:
        try:
            onnx = bajar(f"{RAIZ_PIPER}/{ruta}/{nombre}.onnx", TMP / f"{nombre}.onnx")
            bajar(f"{RAIZ_PIPER}/{ruta}/{nombre}.onnx.json", TMP / f"{nombre}.onnx.json")
            wav = TMP / f"piper-{nombre}.wav"
            subprocess.run([sys.executable, "-m", "piper", "-m", str(onnx),
                            "-f", str(wav)],
                           input=TEXTO_ACENTOS.encode("utf-8"), check=True)
            a_mp3(wav, f"piper-{nombre}", "Piper", nombre, nota)
        except Exception:
            print(f"  fallo {nombre}")
            traceback.print_exc()


# ----------------------------------------------------------- Chatterbox
def chatterbox():
    import torch
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    audio = modelo.generate(TEXTO_ACENTOS, language_id="es")
    wav = TMP / "chatterbox-es.wav"
    torchaudio.save(str(wav), audio, modelo.sr)
    a_mp3(wav, "chatterbox-es", "Chatterbox Multilingual",
          "por defecto (es)", "Neutra, la mas natural si funciona")


PAGINA = """<!doctype html>
<meta charset="utf-8">
<title>Muestras de voz - ByM Solutions</title>
<style>
 body{margin:0;padding:48px 20px;background:#0B3B5C;color:#fff;
   font-family:system-ui,-apple-system,sans-serif;}
 .caja{max-width:640px;margin:0 auto;}
 h1{font-size:28px;margin:0 0 6px;letter-spacing:-.5px;}
 p.int{color:rgba(255,255,255,.7);margin:0 0 34px;line-height:1.5;}
 .v{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);
   border-radius:18px;padding:18px 20px;margin-bottom:14px;}
 .n{font-weight:700;font-size:17px;}
 .d{color:#F2994A;font-size:14px;margin:2px 0 12px;}
 audio{width:100%;}
</style>
<div class="caja">
<h1>Muestras de voz</h1>
<p class="int">Escucha cada una y dime cual te gusta para los reels.
Todas son gratis y se pueden usar comercialmente.</p>
__TARJETAS__
</div>
"""


def pagina():
    tarjetas = []
    for m in hechas:
        tarjetas.append(
            f'<div class="v"><div class="n">{m["motor"]} &middot; {m["voz"]}</div>'
            f'<div class="d">{m["nota"]}</div>'
            f'<audio controls preload="none" src="{m["archivo"]}"></audio></div>')
    (OUT / "index.html").write_text(
        PAGINA.replace("__TARJETAS__", "\n".join(tarjetas)), encoding="utf-8")
    (OUT / "muestras.json").write_text(
        json.dumps(hechas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for nombre, fn in (("Kokoro", kokoro), ("Piper", piper),
                       ("Chatterbox", chatterbox)):
        print(f"\n== {nombre}")
        try:
            fn()
        except Exception:
            print(f"  {nombre} no se pudo generar")
            traceback.print_exc()
    pagina()
    print(f"\n{len(hechas)} muestras listas en muestras/")
