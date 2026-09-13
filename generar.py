#!/usr/bin/env python3
"""
Generador de graficas para Instagram - ByM Solutions.
Convierte texto en imagenes PNG de marca, sin abrir Canva.
Uso: python3 generar.py
"""
import json, pathlib, asyncio
from playwright.async_api import async_playwright

BASE = pathlib.Path(__file__).parent
FONTS = BASE / "fonts"
OUT = BASE / "imagenes"
OUT.mkdir(exist_ok=True)

# Paleta de marca (marca_bym.md)
AZUL = "#0B3B5C"
AMBAR = "#F2994A"
GRIS = "#F5F6F8"
TEXTO = "#1A1A1A"

W, H = 1080, 1350  # formato 4:5, el que mas pantalla ocupa en el feed


def font_face(name, weight, fname):
    return f"""@font-face{{font-family:'{name}';font-weight:{weight};
    src:url('file://{FONTS}/{fname}') format('truetype');}}"""


CSS_BASE = f"""
{font_face('Poppins',400,'Poppins-Regular.ttf')}
{font_face('Poppins',500,'Poppins-Medium.ttf')}
{font_face('Poppins',600,'Poppins-SemiBold.ttf')}
{font_face('Poppins',700,'Poppins-Bold.ttf')}
{font_face('Poppins',800,'Poppins-ExtraBold.ttf')}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:{W}px;height:{H}px;font-family:'Poppins',sans-serif;
 -webkit-font-smoothing:antialiased;overflow:hidden;}}
.card{{width:{W}px;height:{H}px;padding:88px 78px;display:flex;
 flex-direction:column;position:relative;overflow:hidden;}}
.logo{{position:absolute;bottom:70px;left:78px;display:flex;
 align-items:center;gap:14px;z-index:5;}}
.logo .dot{{width:16px;height:16px;border-radius:50%;}}
.logo .txt{{font-size:27px;font-weight:700;letter-spacing:.5px;}}
.chip{{display:inline-block;align-self:flex-start;padding:16px 32px;
 border-radius:100px;font-size:27px;font-weight:700;letter-spacing:2px;
 text-transform:uppercase;margin-bottom:44px;z-index:5;}}
.blob{{position:absolute;border-radius:50%;z-index:0;}}
"""


def tpl_declaracion(d):
    """Fondo ambar completo, alto contraste. Para afirmaciones y llamados a la accion."""
    return f"""<div class="card" style="background:{AMBAR};justify-content:center;">
      <div class="blob" style="width:640px;height:640px;background:rgba(11,59,92,.10);
        top:-230px;right:-210px;"></div>
      <div class="blob" style="width:340px;height:340px;background:rgba(255,255,255,.16);
        bottom:-120px;left:-110px;"></div>
      <div class="chip" style="background:{AZUL};color:#fff;">{d['kicker']}</div>
      <h1 style="font-size:104px;font-weight:800;line-height:1.04;color:{AZUL};
        letter-spacing:-2.5px;z-index:5;">{d['titulo']}</h1>
      <div style="background:{AZUL};height:10px;width:150px;border-radius:6px;
        margin:44px 0 38px;z-index:5;"></div>
      <p style="font-size:41px;font-weight:600;line-height:1.42;
        color:rgba(11,59,92,.86);max-width:830px;z-index:5;">{d['bajada']}</p>
      <div class="logo"><span class="dot" style="background:{AZUL};"></span>
        <span class="txt" style="color:{AZUL};">ByM Solutions</span></div>
    </div>"""


def tpl_lista(d):
    """Tarjetas blancas sobre fondo azul. Para contenido educativo."""
    filas = "".join(f"""
      <div style="display:flex;gap:30px;align-items:center;background:#fff;
        border-radius:28px;padding:34px 36px;margin-bottom:24px;z-index:5;
        box-shadow:0 10px 30px rgba(0,0,0,.16);">
        <div style="width:82px;height:82px;border-radius:50%;background:{AMBAR};
          display:flex;align-items:center;justify-content:center;flex-shrink:0;
          font-size:46px;font-weight:800;color:{AZUL};">{i}</div>
        <div style="font-size:37px;font-weight:600;line-height:1.32;
          color:{AZUL};">{t}</div>
      </div>""" for i, t in enumerate(d['items'], 1))
    return f"""<div class="card" style="background:{AZUL};justify-content:center;">
      <div class="blob" style="width:560px;height:560px;background:#fff;
        opacity:.07;top:-200px;left:-180px;"></div>
      <div class="blob" style="width:220px;height:220px;background:{AMBAR};
        bottom:120px;right:-70px;opacity:.9;"></div>
      <div class="chip" style="background:{AMBAR};color:{AZUL};">{d['kicker']}</div>
      <h1 style="font-size:84px;font-weight:800;line-height:1.08;
        color:#fff;letter-spacing:-1.8px;margin-bottom:52px;z-index:5;">{d['titulo']}</h1>
      <div>{filas}</div>
      <div class="logo"><span class="dot" style="background:{AMBAR};"></span>
        <span class="txt" style="color:#fff;">ByM Solutions</span></div>
    </div>"""


def tpl_pasos(d):
    """Bloque ambar arriba, pasos en tarjetas abajo. Para explicar como funciona algo."""
    filas = ""
    for i, (ic, t) in enumerate(d['pasos'], 1):
        filas += f"""
        <div style="display:flex;gap:28px;align-items:center;
          background:rgba(255,255,255,.09);border:2px solid rgba(255,255,255,.20);
          border-radius:30px;padding:42px 38px;margin-bottom:30px;">
          <div style="width:92px;height:92px;border-radius:24px;background:{AMBAR};
            display:flex;align-items:center;justify-content:center;flex-shrink:0;
            font-size:48px;font-weight:800;color:{AZUL};">{ic}</div>
          <div style="font-size:40px;font-weight:600;line-height:1.3;
            color:#fff;">{t}</div>
        </div>"""
    return f"""<div class="card" style="background:{AZUL};padding:0;">
      <div style="background:{AMBAR};padding:80px 78px 64px;position:relative;
        overflow:hidden;">
        <div class="blob" style="width:400px;height:400px;background:rgba(11,59,92,.10);
          top:-170px;right:-130px;"></div>
        <div class="chip" style="background:{AZUL};color:#fff;margin-bottom:30px;">
          {d['kicker']}</div>
        <h1 style="font-size:92px;font-weight:800;line-height:1.05;color:{AZUL};
          letter-spacing:-2px;z-index:5;position:relative;">{d['titulo']}</h1>
      </div>
      <div style="padding:0 78px 150px;flex:1;display:flex;
        flex-direction:column;justify-content:center;">{filas}</div>
      <div class="logo"><span class="dot" style="background:{AMBAR};"></span>
        <span class="txt" style="color:#fff;">ByM Solutions</span></div>
    </div>"""


PLANTILLAS = {"declaracion": tpl_declaracion, "lista": tpl_lista, "pasos": tpl_pasos}


async def render(posts):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--font-render-hinting=none"])
        pg = await b.new_page(viewport={"width": W, "height": H},
                              device_scale_factor=1)
        for post in posts:
            html = f"<html><head><style>{CSS_BASE}</style></head><body>" \
                   f"{PLANTILLAS[post['plantilla']](post)}</body></html>"
            await pg.set_content(html)
            await pg.wait_for_timeout(320)  # que carguen las fuentes
            ruta = OUT / f"{post['id']}.png"
            await pg.screenshot(path=str(ruta))
            print(f"  generado: {ruta.name}")
        await b.close()


if __name__ == "__main__":
    posts = json.loads((BASE / "calendario.json").read_text(encoding="utf-8"))
    # Los reels no llevan grafica: los arma medios.py. Aca van las entradas
    # con plantilla propia (fotos) y las laminas de cada carrusel.
    graficas = []
    for p in posts:
        if p.get("plantilla"):
            graficas.append(p)
        graficas.extend(p.get("laminas", []))
    print(f"Generando {len(graficas)} graficas...")
    asyncio.run(render(graficas))
    print(f"Listo. Carpeta: {OUT}")
