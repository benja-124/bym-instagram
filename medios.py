#!/usr/bin/env python3
"""
Genera los reels de ByM Solutions: cuadro por cuadro con Playwright,
armado con ffmpeg, y musica de fondo sintetizada aca mismo (sin licencias
de terceros). Salida: medios/<id>.mp4
"""
import asyncio
import pathlib
import subprocess

from playwright.async_api import async_playwright

BASE = pathlib.Path(__file__).parent
FONTS = BASE / "fonts"
OUT = BASE / "medios"
TMP = BASE / "_cuadros"
OUT.mkdir(exist_ok=True)

AZUL, AMBAR = "#0B3B5C", "#F2994A"
W, H, FPS = 1080, 1920, 20

CSS = f"""
@font-face{{font-family:'P';font-weight:800;
  src:url('file://{FONTS}/Poppins-ExtraBold.ttf') format('truetype');}}
@font-face{{font-family:'P';font-weight:600;
  src:url('file://{FONTS}/Poppins-SemiBold.ttf') format('truetype');}}
@font-face{{font-family:'P';font-weight:500;
  src:url('file://{FONTS}/Poppins-Medium.ttf') format('truetype');}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{W}px;height:{H}px;background:{AZUL};font-family:'P',sans-serif;
  -webkit-font-smoothing:antialiased;overflow:hidden;}}
#e{{width:{W}px;height:{H}px;position:relative;overflow:hidden;padding:0 96px;
  display:flex;flex-direction:column;justify-content:center;}}
.blob{{position:absolute;border-radius:50%;background:{AMBAR};opacity:.14;}}
.kick{{font-size:40px;font-weight:800;letter-spacing:4px;text-transform:uppercase;
  color:{AMBAR};margin-bottom:36px;}}
.tit{{font-size:118px;font-weight:800;line-height:1.03;color:#fff;letter-spacing:-3px;}}
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
.marca{{position:absolute;bottom:110px;left:96px;font-size:40px;font-weight:800;
  color:{AMBAR};letter-spacing:1px;}}
.sub{{position:absolute;bottom:230px;left:96px;right:96px;text-align:center;
  font-size:44px;font-weight:600;color:#fff;text-shadow:0 3px 18px rgba(0,0,0,.6);}}
"""

# Guion del reel. El gancho arranca con movimiento inmediato: segun los datos
# hay que mover algo en el primer segundo y medio o la gente se va.
JS = """
function ease(t){return t<0?0:t>1?1:1-Math.pow(1-t,3);}
function seg(t,a,b){return ease((t-a)/(b-a));}
function sub(txt,t,a,b){return (t>=a&&t<b)?'<div class="sub">'+txt+'</div>':'';}
function pintar(t){
  var E=document.getElementById('e');
  var h='<div class="blob" style="width:820px;height:820px;top:-300px;right:-280px;"></div>';
  if(t<2.2){
    var o=seg(t,0.0,0.45), s=seg(t,0.0,0.7);
    h+='<div style="opacity:'+o+';transform:translateY('+((1-s)*60)+'px) scale('+(0.94+0.06*s)+')">'
      +'<div class="kick">Así funciona</div>'
      +'<div class="tit">Tu stock se<br>descuenta solo</div></div>';
    h+=sub('Tu stock se descuenta solo',t,0.5,2.2);
  }
  else if(t<5.6){
    var a=seg(t,2.3,2.8), b=seg(t,3.3,3.8), c=seg(t,4.4,4.9);
    h+='<div style="display:flex;flex-direction:column;">'
      +'<div class="burb ent" style="opacity:'+a+';transform:translateY('+((1-a)*30)+'px)">Llegaron 24 cervezas</div>'
      +'<div class="burb sal" style="opacity:'+b+';transform:translateY('+((1-b)*30)+'px)">Anotado. Quedan 48 en total.</div>'
      +'<div class="burb ent" style="opacity:'+c+';transform:translateY('+((1-c)*30)+'px)">Vendí 40 hoy</div></div>';
    h+=sub('Avisas por mensaje, como siempre',t,2.4,5.6);
  }
  else if(t<8.2){
    var p=seg(t,5.9,7.3), o2=seg(t,5.8,6.2);
    var n=Math.round(48-(48-8)*p);
    h+='<div class="tarj" style="opacity:'+o2+'">'
      +'<div class="lab">Cerveza 350 ml</div>'
      +'<div class="num">'+n+'</div>'
      +'<div class="lab">unidades en bodega</div></div>';
    h+=sub('El sistema lleva la cuenta',t,5.9,8.2);
  }
  else if(t<10.6){
    var o3=seg(t,8.3,8.7), k=1+0.03*Math.sin(t*9);
    h+='<div class="alerta" style="opacity:'+o3+';transform:scale('+(o3*k)+')">'
      +'<div style="font-size:40px;font-weight:800;letter-spacing:3px;text-transform:uppercase;margin-bottom:22px;">Alerta</div>'
      +'<div style="font-size:62px;font-weight:800;line-height:1.15;">Quedan 8 cervezas.<br>Hora de pedir.</div></div>';
    h+=sub('Te avisa antes de que se acabe',t,8.4,10.6);
  }
  else{
    var o4=seg(t,10.7,11.1);
    var prods=[['Cerveza',8,16,'#F2994A'],['Bebidas',34,70,'#7FB7E8'],
               ['Snacks',52,100,'#7FE8B0'],['Cigarros',21,45,'#F2994A']];
    var f='';
    for(var i=0;i<prods.length;i++){
      var pr=prods[i];
      var g=seg(t,10.9+i*0.10,11.6+i*0.10);
      f+='<div class="fila" style="opacity:'+seg(t,10.8+i*0.10,11.2+i*0.10)+'">'
        +'<div class="pnom">'+pr[0]+'</div>'
        +'<div class="barra"><i style="width:'+((pr[1]/pr[2])*100*g)+'%;background:'+pr[3]+'"></i></div>'
        +'<div class="pval">'+pr[1]+'</div></div>';
    }
    h+='<div style="opacity:'+o4+'"><div class="kick">Tu bodega, siempre al día</div>'+f+'</div>';
    h+=sub('Todo tu inventario, en un vistazo',t,10.9,13.0);
  }
  h+='<div class="marca">ByM Solutions</div>';
  E.innerHTML=h;
}
"""


async def cuadros(dur):
    TMP.mkdir(exist_ok=True)
    total = int(dur * FPS)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--font-render-hinting=none"])
        pg = await b.new_page(viewport={"width": W, "height": H})
        await pg.set_content(
            f"<html><head><style>{CSS}</style></head><body><div id='e'></div>"
            f"<script>{JS}</script></body></html>")
        await pg.wait_for_timeout(400)
        for i in range(total):
            await pg.evaluate(f"pintar({i / FPS})")
            await pg.screenshot(path=str(TMP / f"f{i:04d}.png"))
        await b.close()
    print(f"  {total} cuadros")


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
        "-map", "[o]", "-c:a", "aac", "-b:a", "128k", str(ruta)], check=True)


def armar(ident, dur):
    aud = TMP / "pad.m4a"
    musica(dur, aud)
    salida = OUT / f"{ident}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-i", str(TMP / "f%04d.png"),
        "-i", str(aud), "-map", "0:v", "-map", "1:a", "-shortest",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(salida)], check=True)
    print(f"  {salida.name} listo")


async def main():
    ident, dur = "reel-como-funciona", 13.0
    print(f"Generando {ident} ({dur}s)")
    await cuadros(dur)
    armar(ident, dur)
    for f in TMP.glob("*.png"):
        f.unlink()


if __name__ == "__main__":
    asyncio.run(main())
