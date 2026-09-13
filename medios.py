#!/usr/bin/env python3
"""
Arma los reels de ByM Solutions.

La duracion de cada escena sale del audio: voz.py deja un wav por escena
y un tiempos.json con lo que dura cada una, y aca se dibuja exactamente
ese tiempo. Asi la imagen, el subtitulo y la voz nunca se desfasan.

Cuadro por cuadro con Playwright, armado con ffmpeg. La musica de fondo
se sintetiza aca mismo, sin licencias de terceros.

Uso:  python3 medios.py                     arma todos los reels
      python3 medios.py reel-como-funciona  arma solo uno
"""
import asyncio
import base64
import json
import pathlib
import shutil
import subprocess
import sys

from playwright.async_api import async_playwright

BASE = pathlib.Path(__file__).parent
FONTS = BASE / "fonts"


def fuente(nombre):
    """Devuelve el .ttf en base64 para incrustarlo en el CSS.

    Con url('file://...') Chromium no la carga: la pagina se arma con
    set_content, su origen es about:blank, y cargar un archivo local
    desde ahi esta bloqueado. En GitHub Actions eso dejaba todos los
    reels con la tipografia por defecto, en silencio.
    """
    return base64.b64encode((FONTS / nombre).read_bytes()).decode()
VOZ = BASE / "voz"
OUT = BASE / "medios"
IMAGENES = BASE / "imagenes"
TMP = BASE / "_cuadros"
OUT.mkdir(exist_ok=True)
IMAGENES.mkdir(exist_ok=True)

AZUL, AMBAR = "#0B3B5C", "#F2994A"
W, H, FPS = 1080, 1920, 20

CSS = f"""
@font-face{{font-family:'Poppins';font-weight:800;
  src:url(data:font/ttf;base64,{fuente('Poppins-ExtraBold.ttf')}) format('truetype');}}
@font-face{{font-family:'Poppins';font-weight:600;
  src:url(data:font/ttf;base64,{fuente('Poppins-SemiBold.ttf')}) format('truetype');}}
@font-face{{font-family:'Poppins';font-weight:500;
  src:url(data:font/ttf;base64,{fuente('Poppins-Medium.ttf')}) format('truetype');}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{W}px;height:{H}px;background:{AZUL};font-family:'Poppins',sans-serif;
  -webkit-font-smoothing:antialiased;overflow:hidden;}}
#e{{width:{W}px;height:{H}px;position:relative;overflow:hidden;padding:0 96px;
  display:flex;flex-direction:column;justify-content:center;}}
.blob{{position:absolute;border-radius:50%;background:{AMBAR};opacity:.14;}}
.kick{{font-size:40px;font-weight:800;letter-spacing:4px;text-transform:uppercase;
  color:{AMBAR};margin-bottom:36px;}}
.tit{{font-size:112px;font-weight:800;line-height:1.04;color:#fff;letter-spacing:-3px;}}
.burb{{max-width:660px;padding:38px 46px;border-radius:40px;font-size:46px;
  font-weight:500;line-height:1.3;margin-bottom:30px;}}
.ent{{background:#fff;color:{AZUL};border-bottom-left-radius:12px;align-self:flex-start;}}
.sal{{background:{AMBAR};color:{AZUL};border-bottom-right-radius:12px;
  align-self:flex-end;font-weight:600;}}
.tarj{{background:rgba(255,255,255,.10);border:3px solid rgba(255,255,255,.22);
  border-radius:44px;padding:56px;}}
.num{{font-size:190px;font-weight:800;color:#fff;line-height:1;letter-spacing:-6px;}}
.lab{{font-size:44px;font-weight:600;color:rgba(255,255,255,.75);}}
.alerta{{background:{AMBAR};border-radius:44px;padding:52px 56px;color:{AZUL};}}
.fila{{display:flex;align-items:center;gap:28px;margin-bottom:34px;}}
.barra{{flex:1;height:30px;border-radius:16px;background:rgba(255,255,255,.16);
  overflow:hidden;}}
.barra i{{display:block;height:100%;border-radius:16px;}}
.pnom{{font-size:38px;font-weight:600;color:#fff;width:270px;}}
.pval{{font-size:38px;font-weight:800;color:{AMBAR};width:90px;text-align:right;}}
.nro{{font-size:150px;font-weight:800;color:{AMBAR};line-height:.9;
  letter-spacing:-6px;margin-bottom:20px;}}
.cap{{font-size:88px;font-weight:800;color:#fff;line-height:1.08;letter-spacing:-2px;}}
.det{{font-size:48px;font-weight:500;color:rgba(255,255,255,.78);
  line-height:1.35;margin-top:34px;}}
.pill{{display:inline-block;background:{AMBAR};color:{AZUL};border-radius:100px;
  padding:20px 42px;font-size:40px;font-weight:800;letter-spacing:2px;
  text-transform:uppercase;}}
.marca{{position:absolute;bottom:110px;left:96px;font-size:40px;font-weight:800;
  color:{AMBAR};letter-spacing:1px;}}
.sub{{position:absolute;bottom:230px;left:96px;right:96px;text-align:center;
  font-size:44px;font-weight:700;color:#fff;line-height:1.25;
  text-shadow:0 3px 18px rgba(0,0,0,.65);}}
"""

# Las escenas se inyectan como JSON en __ESCENAS__.
JS = """
var ESC = __ESCENAS__;

function ease(t){ return t<0?0 : t>1?1 : 1-Math.pow(1-t,3); }
function seg(t,a,b){ return ease((t-a)/(b-a)); }

var PLANTILLAS = {

  gancho: function(d,u){
    var o=seg(u,0,0.45), s=seg(u,0,0.7);
    return '<div style="opacity:'+o+';transform:translateY('+((1-s)*60)+'px) scale('+(0.94+0.06*s)+')">'
      + '<div class="kick">'+d.kicker+'</div>'
      + '<div class="tit">'+d.titulo+'</div></div>';
  },

  chat: function(d,u,dur){
    var paso = Math.max(0.55, (dur-0.5)/d.mensajes.length);
    var h = '<div style="display:flex;flex-direction:column;">';
    for(var i=0;i<d.mensajes.length;i++){
      var a = seg(u, i*paso, i*paso+0.45);
      h += '<div class="burb '+d.mensajes[i][0]+'" style="opacity:'+a
         + ';transform:translateY('+((1-a)*30)+'px)">'+d.mensajes[i][1]+'</div>';
    }
    return h+'</div>';
  },

  contador: function(d,u,dur){
    var o = seg(u,0,0.35);
    var p = seg(u, 0.3, Math.max(0.9, dur-0.5));
    var n = Math.round(d.desde - (d.desde-d.hasta)*p);
    return '<div class="tarj" style="opacity:'+o+'">'
      + '<div class="lab">'+d.arriba+'</div>'
      + '<div class="num">'+n+'</div>'
      + '<div class="lab">'+d.abajo+'</div></div>';
  },

  alerta: function(d,u){
    var o = seg(u,0,0.35), k = 1+0.03*Math.sin(u*9);
    return '<div class="alerta" style="opacity:'+o+';transform:scale('+(o*k)+')">'
      + '<div style="font-size:40px;font-weight:800;letter-spacing:3px;'
      + 'text-transform:uppercase;margin-bottom:22px;">'+d.etiqueta+'</div>'
      + '<div style="font-size:62px;font-weight:800;line-height:1.15;">'+d.texto+'</div></div>';
  },

  tablero: function(d,u){
    var o = seg(u,0,0.35), f = '';
    for(var i=0;i<d.filas.length;i++){
      var r = d.filas[i];
      var g = seg(u, 0.2+i*0.10, 0.9+i*0.10);
      f += '<div class="fila" style="opacity:'+seg(u,0.15+i*0.10,0.5+i*0.10)+'">'
         + '<div class="pnom">'+r[0]+'</div>'
         + '<div class="barra"><i style="width:'+((r[1]/r[2])*100*g)+'%;background:'+r[3]+'"></i></div>'
         + '<div class="pval">'+r[1]+'</div></div>';
    }
    return '<div style="opacity:'+o+'"><div class="kick">'+d.kicker+'</div>'+f+'</div>';
  },

  capacidad: function(d,u){
    var o = seg(u,0,0.45), s = seg(u,0,0.75);
    return '<div style="opacity:'+o+';transform:translateY('+((1-s)*50)+'px)">'
      + '<div class="nro">'+d.n+'</div>'
      + '<div class="cap">'+d.titulo+'</div>'
      + '<div class="det">'+d.detalle+'</div></div>';
  },

  cierre: function(d,u){
    var o = seg(u,0,0.45);
    return '<div style="opacity:'+o+'">'
      + '<div class="pill">'+d.pill+'</div>'
      + '<div class="tit" style="margin-top:46px;">'+d.titulo+'</div>'
      + '<div class="det">'+d.detalle+'</div></div>';
  }
};

function pintar(t){
  var E = document.getElementById('e');
  var esc = ESC[ESC.length-1], u = esc.fin - esc.inicio;
  for(var i=0;i<ESC.length;i++){
    if(t >= ESC[i].inicio && t < ESC[i].fin){ esc = ESC[i]; u = t - ESC[i].inicio; break; }
  }
  var h = '<div class="blob" style="width:820px;height:820px;top:-300px;right:-280px;"></div>';
  h += PLANTILLAS[esc.plantilla](esc.datos, u, esc.fin - esc.inicio);
  if(u > 0.12 && esc.sub){
    h += '<div class="sub">'+esc.sub+'</div>';
  }
  h += '<div class="marca">ByM Solutions</div>';
  E.innerHTML = h;
}
"""


def linea_de_tiempo(tiempos):
    """Convierte las duraciones del audio en escenas con inicio y fin."""
    escenas, reloj = [], 0.0
    for e in tiempos["escenas"]:
        largo = e["dur"] + e["pausa"]
        escenas.append({"plantilla": e["plantilla"], "datos": e["datos"],
                        "sub": e["sub"], "durvoz": e["dur"],
                        "inicio": round(reloj, 3),
                        "fin": round(reloj + largo, 3)})
        reloj += largo
    return escenas, round(reloj, 3)


async def cuadros(escenas, dur, tmp):
    tmp.mkdir(exist_ok=True, parents=True)
    total = int(dur * FPS)
    js = JS.replace("__ESCENAS__", json.dumps(escenas, ensure_ascii=False))
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--font-render-hinting=none"])
        pg = await b.new_page(viewport={"width": W, "height": H})
        await pg.set_content(
            f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body><div id='e'></div><script>{js}</script></body></html>")
        await pg.wait_for_timeout(500)
        for i in range(total):
            await pg.evaluate(f"pintar({i / FPS})")
            await pg.screenshot(path=str(tmp / f"f{i:04d}.png"))
        await b.close()
    print(f"  {total} cuadros")
    return total


def portada(reel, escenas, tmp):
    """Guarda un cuadro de la primera escena como miniatura del reel.

    Sin cover_url, Instagram toma el primer cuadro del video, que cae a
    mitad del fundido de entrada y deja la cuadricula casi vacia. Aca se
    elige un cuadro avanzado dentro de la primera escena: la animacion ya
    termino y todavia no empieza la siguiente.
    """
    primera = escenas[0]
    largo = primera["fin"] - primera["inicio"]
    # 75% de la escena, nunca antes de 0.9s (ahi ya cerro el fundido).
    t = primera["inicio"] + min(max(0.9, largo * 0.75), largo - 1 / FPS)
    cuadro = tmp / f"f{int(t * FPS):04d}.png"
    if not cuadro.exists():
        print(f"  aviso: no existe el cuadro de portada ({cuadro.name})")
        return
    destino = IMAGENES / f"{reel}-portada.png"
    shutil.copyfile(cuadro, destino)
    print(f"  portada: {destino.name} (t={t:.2f}s)")


def locucion(carpeta, tiempos, destino):
    """Pega las escenas habladas con su pausa detras de cada una."""
    lista = carpeta / "_lista.txt"
    partes = []
    for e in tiempos["escenas"]:
        origen = carpeta / f"{e['id']}.wav"
        pieza = carpeta / f"_p_{e['id']}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(origen), "-af", f"apad=pad_dur={e['pausa']}",
            "-t", str(e["dur"] + e["pausa"]), "-ar", "44100", "-ac", "1",
            str(pieza)], check=True)
        partes.append(pieza)
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes),
                     encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(lista),
        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1", str(destino)],
        check=True, cwd=str(carpeta))
    for p in partes:
        p.unlink()
    lista.unlink()


def musica(dur, ruta):
    """Colchon ambiental sintetizado: sin derechos de terceros."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur+1}",
        "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur+1}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur+1}",
        "-filter_complex",
        "[0]volume=0.25,tremolo=f=0.5:d=0.3[a];"
        "[1]volume=0.16,tremolo=f=0.33:d=0.4[b];"
        "[2]volume=0.09,tremolo=f=0.25:d=0.5[c];"
        "[a][b][c]amix=inputs=3:normalize=0,aecho=0.8:0.9:120:0.25,"
        "highpass=f=90,lowpass=f=2600,"
        f"afade=t=in:st=0:d=1.5,afade=t=out:st={dur-1.5}:d=1.5,volume=0.7[o]",
        "-map", "[o]", "-c:a", "pcm_s16le", "-ar", "44100", str(ruta)],
        check=True)


def mezclar(voz_wav, mus_wav, destino):
    """La musica queda de fondo y baja sola cuando hay voz."""
    entradas = ["-i", str(mus_wav)]
    if voz_wav is not None:
        entradas = ["-i", str(voz_wav), "-i", str(mus_wav)]
        filtro = ("[1]volume=0.30[m];"
                  "[m][0]sidechaincompress=threshold=0.04:ratio=9:"
                  "attack=15:release=320[md];"
                  "[0][md]amix=inputs=2:normalize=0,"
                  "loudnorm=I=-14:TP=-1.5:LRA=11[o]")
    else:
        filtro = "[0]volume=0.8,loudnorm=I=-16:TP=-1.5:LRA=11[o]"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    *entradas, "-filter_complex", filtro, "-map", "[o]",
                    "-c:a", "aac", "-b:a", "160k", str(destino)], check=True)


def armar(ident, dur, tmp, audio):
    salida = OUT / f"{ident}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-i", str(tmp / "f%04d.png"),
        "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(salida)], check=True)
    print(f"  {salida.name} listo ({dur:.1f}s)")


async def hacer(reel):
    carpeta = VOZ / reel
    archivo = carpeta / "tiempos.json"
    if not archivo.exists():
        print(f"{reel}: falta la locucion. Corre voz.py primero.")
        return
    tiempos = json.loads(archivo.read_text(encoding="utf-8"))
    escenas, dur = linea_de_tiempo(tiempos)
    print(f"{reel} ({dur:.1f}s, voz: {tiempos.get('motor', '?')})")

    tmp = TMP / reel
    await cuadros(escenas, dur, tmp)
    portada(reel, escenas, tmp)

    voz_wav = carpeta / "_locucion.wav"
    locucion(carpeta, tiempos, voz_wav)
    mus_wav = carpeta / "_musica.wav"
    musica(dur, mus_wav)
    audio = carpeta / "_audio.m4a"
    mezclar(voz_wav, mus_wav, audio)

    armar(reel, dur, tmp, audio)

    for f in tmp.glob("*.png"):
        f.unlink()
    for f in (voz_wav, mus_wav, audio):
        f.unlink(missing_ok=True)


async def main():
    pedidos = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not pedidos:
        if not VOZ.exists():
            print("No hay locucion todavia. Corre voz.py primero.")
            return
        pedidos = sorted(d.name for d in VOZ.iterdir() if d.is_dir())
    for reel in pedidos:
        await hacer(reel)


if __name__ == "__main__":
    asyncio.run(main())
