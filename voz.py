#!/usr/bin/env python3
"""
Genera la locucion de los reels a partir de guion.json.

Motores (se elige con la variable de entorno VOZ_MOTOR):
  kokoro   gratis, sin cuenta ni tarjeta   Apache 2.0
  piper    gratis, sin cuenta ni tarjeta   MIT
  google   Google Cloud Chirp 3 HD         necesita el secreto GOOGLE_TTS_KEY

Deja un wav por escena en voz/<reel>/ y un tiempos.json con la duracion
real de cada una. medios.py arma el video con esas duraciones, asi la
imagen siempre va sincronizada con lo que se escucha.

Uso:  python3 voz.py            genera todo lo que falte
      python3 voz.py --todo     regenera aunque ya exista
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

BASE = pathlib.Path(__file__).parent
GUION = BASE / "guion.json"
VOZ = BASE / "voz"
MODELOS = BASE / "_modelos"
VOZ.mkdir(exist_ok=True)
MODELOS.mkdir(exist_ok=True)

MOTOR = os.environ.get("VOZ_MOTOR", "kokoro").strip().lower()
VOZ_KOKORO = os.environ.get("VOZ_KOKORO", "ef_dora").strip()
VOZ_PIPER = os.environ.get("VOZ_PIPER", "es_MX-claude-high").strip()
VOZ_GOOGLE = os.environ.get("VOZ_GOOGLE", "es-US-Chirp3-HD-Aoede").strip()

RAIZ_PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
RUTAS_PIPER = {
    "es_MX-claude-high": "es/es_MX/claude/high",
    "es_MX-ald-medium": "es/es_MX/ald/medium",
    "es_AR-daniela-high": "es/es_AR/daniela/high",
    "es_ES-davefx-medium": "es/es_ES/davefx/medium",
}

_kokoro = None


def duracion(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(ruta)],
                       capture_output=True, text=True, check=True)
    return round(float(r.stdout.strip()), 3)


def limpiar(wav):
    """Deja la voz pareja y recorta el silencio de los extremos."""
    temp = wav.with_suffix(".tmp.wav")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav),
        "-af", ("silenceremove=start_periods=1:start_silence=0.05:"
                "start_threshold=-45dB,"
                "areverse,"
                "silenceremove=start_periods=1:start_silence=0.05:"
                "start_threshold=-45dB,"
                "areverse,"
                "loudnorm=I=-16:TP=-1.5:LRA=11"),
        "-ar", "44100", "-ac", "1", str(temp)], check=True)
    temp.replace(wav)


# --------------------------------------------------------------- motores
def con_kokoro(texto, destino):
    global _kokoro
    import numpy as np
    import soundfile as sf
    if _kokoro is None:
        from kokoro import KPipeline
        _kokoro = KPipeline(lang_code="e")
    trozos = [a for _, _, a in _kokoro(texto, voice=VOZ_KOKORO, speed=1.0)]
    sf.write(destino, np.concatenate(trozos), 24000)


def con_piper(texto, destino):
    ruta = RUTAS_PIPER[VOZ_PIPER]
    onnx = MODELOS / f"{VOZ_PIPER}.onnx"
    if not onnx.exists():
        urllib.request.urlretrieve(f"{RAIZ_PIPER}/{ruta}/{VOZ_PIPER}.onnx", onnx)
        urllib.request.urlretrieve(f"{RAIZ_PIPER}/{ruta}/{VOZ_PIPER}.onnx.json",
                                   MODELOS / f"{VOZ_PIPER}.onnx.json")
    subprocess.run([sys.executable, "-m", "piper", "-m", str(onnx),
                    "-f", str(destino)],
                   input=texto.encode("utf-8"), check=True)


def con_google(texto, destino):
    """Chirp 3 HD. El secreto GOOGLE_TTS_KEY es el JSON de la cuenta de servicio."""
    from google.cloud import texttospeech
    from google.oauth2 import service_account
    bruto = os.environ.get("GOOGLE_TTS_KEY", "")
    if not bruto:
        raise SystemExit("Falta el secreto GOOGLE_TTS_KEY")
    cred = service_account.Credentials.from_service_account_info(json.loads(bruto))
    cliente = texttospeech.TextToSpeechClient(credentials=cred)
    idioma = "-".join(VOZ_GOOGLE.split("-")[:2])
    r = cliente.synthesize_speech(
        input=texttospeech.SynthesisInput(text=texto),
        voice=texttospeech.VoiceSelectionParams(language_code=idioma,
                                                name=VOZ_GOOGLE),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000))
    destino.write_bytes(r.audio_content)


MOTORES = {"kokoro": con_kokoro, "piper": con_piper, "google": con_google}


# ----------------------------------------------------------------- main
def main():
    rehacer = "--todo" in sys.argv
    if MOTOR not in MOTORES:
        raise SystemExit(f"Motor desconocido: {MOTOR}")
    guion = json.loads(GUION.read_text(encoding="utf-8"))
    hablar = MOTORES[MOTOR]
    print(f"Motor: {MOTOR}")

    for reel, datos in guion.items():
        carpeta = VOZ / reel
        carpeta.mkdir(exist_ok=True)
        tiempos = []
        print(f"\n{reel}")
        for escena in datos["escenas"]:
            wav = carpeta / f"{escena['id']}.wav"
            if rehacer or not wav.exists():
                hablar(escena["voz"], wav)
                limpiar(wav)
                print(f"  {escena['id']}  generada")
            else:
                print(f"  {escena['id']}  ya estaba")
            tiempos.append({
                "id": escena["id"],
                "dur": duracion(wav),
                "pausa": escena.get("pausa", 0.35),
                "plantilla": escena["plantilla"],
                "datos": escena.get("datos", {}),
                "sub": escena.get("sub", escena["voz"]),
            })
        (carpeta / "tiempos.json").write_text(
            json.dumps({"motor": MOTOR, "escenas": tiempos},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total = sum(e["dur"] + e["pausa"] for e in tiempos)
        print(f"  total {total:.1f}s")


if __name__ == "__main__":
    main()
