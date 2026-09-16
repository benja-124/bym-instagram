#!/usr/bin/env python3
"""
Revisa que ningun texto de los reels quede debajo de la interfaz de Instagram.

Instagram dibuja su propia interfaz encima del video: abajo el nombre de la
cuenta, el pie y el audio (unos 320 px de los 1920), a la derecha la columna
de me gusta, comentar, compartir y guardar (unos 120 px), y arriba una franja
de unos 110 px. Lo que caiga ahi no se lee en el telefono.

Esto pinta cada escena en su punto medio y mide donde queda cada texto.

Uso:  python3 zonas.py            revisa todos los reels
      python3 zonas.py reel-hora  revisa uno
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

import medios

BASE = pathlib.Path(__file__).parent

MARGEN_ARRIBA = 110
MARGEN_ABAJO = 320
MARGEN_DERECHA = 120

LIMITE_DER = medios.W - MARGEN_DERECHA
LIMITE_ABAJO = medios.H - MARGEN_ABAJO


async def revisar(reels):
    problemas = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--font-render-hinting=none"])
        pg = await b.new_page(viewport={"width": medios.W, "height": medios.H})
        for reel in reels:
            archivo = medios.VOZ / reel / "tiempos.json"
            if not archivo.exists():
                continue
            tiempos = json.loads(archivo.read_text(encoding="utf-8"))
            escenas, dur = medios.linea_de_tiempo(tiempos)
            js = medios.JS.replace("__ESCENAS__",
                                   json.dumps(escenas, ensure_ascii=False))
            await pg.set_content(
                f"<html><head><meta charset='utf-8'><style>{medios.CSS}</style>"
                f"</head><body><div id='e'></div><script>{js}</script></body></html>")
            await pg.wait_for_timeout(300)
            for esc in escenas:
                medio = (esc["inicio"] + esc["fin"]) / 2
                await pg.evaluate(f"pintar({medio})")
                # Se mide el texto en si, renglon por renglon, no la caja del
                # elemento: un div de bloque ocupa todo el ancho aunque la
                # frase termine antes, y eso daria falsos positivos en todo.
                cajas = await pg.evaluate("""() => {
                  const out = [];
                  const rec = document.createRange();
                  const paseo = document.createTreeWalker(
                      document.getElementById('e'), NodeFilter.SHOW_TEXT);
                  let n;
                  while ((n = paseo.nextNode())) {
                    const t = n.textContent.trim();
                    if (!t) continue;
                    rec.selectNodeContents(n);
                    for (const r of rec.getClientRects()) {
                      if (r.width < 4 || r.height < 4) continue;
                      out.push({t: t.slice(0, 40), x: Math.round(r.right),
                                y: Math.round(r.bottom),
                                top: Math.round(r.top)});
                    }
                  }
                  // Los fondos de color tambien cuentan: una burbuja o una
                  // tarjeta cortada por la columna de botones se ve mal igual.
                  document.querySelectorAll('.burb,.alerta,.tarj,.pill,.barra')
                    .forEach(el => {
                      const r = el.getBoundingClientRect();
                      out.push({t: '[' + el.className + ']',
                                x: Math.round(r.right), y: Math.round(r.bottom),
                                top: Math.round(r.top)});
                    });
                  return out;
                }""")
                # Los titulares llevan sus saltos de linea escritos a mano con
                # <br>. Si ademas se parten solos, la frase queda cortada en un
                # lugar raro: eso es senal de que el texto ya no cabe.
                partidos = await pg.evaluate("""() => {
                  const out = [];
                  document.querySelectorAll('.tit,.cap').forEach(el => {
                    const rec = document.createRange();
                    el.childNodes.forEach(n => {
                      if (n.nodeType !== 3 || !n.textContent.trim()) return;
                      rec.selectNodeContents(n);
                      const k = rec.getClientRects().length;
                      if (k > 1) out.push([n.textContent.trim(), k]);
                    });
                  });
                  return out;
                }""")
                for txt, k in partidos:
                    problemas.append(
                        f"{reel} / {esc['plantilla']}: \"{txt}\" se parte solo "
                        f"en {k} renglones; pon un <br> en guion.json o acorta "
                        f"la frase")

                for c in cajas:
                    if c["x"] > LIMITE_DER:
                        problemas.append(
                            f"{reel} / {esc['plantilla']}: \"{c['t']}\" llega a "
                            f"x={c['x']} (la columna de botones empieza en "
                            f"{LIMITE_DER})")
                    if c["y"] > LIMITE_ABAJO:
                        problemas.append(
                            f"{reel} / {esc['plantilla']}: \"{c['t']}\" baja a "
                            f"y={c['y']} (el pie de Instagram empieza en "
                            f"{LIMITE_ABAJO})")
                    if c["y"] > medios.H or c["top"] < 0:
                        problemas.append(
                            f"{reel} / {esc['plantilla']}: \"{c['t']}\" se "
                            f"sale del cuadro (arriba={c['top']}, "
                            f"abajo={c['y']})")
                    elif c["top"] < MARGEN_ARRIBA:
                        problemas.append(
                            f"{reel} / {esc['plantilla']}: \"{c['t']}\" sube a "
                            f"y={c['top']} (la franja de arriba llega a "
                            f"{MARGEN_ARRIBA})")
        await b.close()
    return problemas


def main():
    pedidos = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not pedidos:
        pedidos = sorted(d.name for d in medios.VOZ.iterdir() if d.is_dir())
    problemas = asyncio.run(revisar(pedidos))
    if not problemas:
        print(f"Todos los textos quedan a la vista y ningun titular se parte "
              f"solo ({len(pedidos)} reels).")
        return 0
    print(f"{len(problemas)} texto(s) tapados por la interfaz de Instagram:\n")
    for p in problemas:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
