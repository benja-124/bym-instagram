#!/usr/bin/env python3
"""
Renueva el token de larga duracion de Instagram (dura 60 dias).

Se ejecuta una vez al mes desde GitHub Actions. Si existe un PAT de GitHub
con permiso para escribir secretos, guarda el token nuevo automaticamente.
Si no existe, avisa cuantos dias quedan para que lo renueves a mano.

Variables de entorno:
  IG_TOKEN        token actual (secreto de GitHub)
  GH_PAT          opcional: token personal de GitHub con permiso 'secrets: write'
  GITHUB_REPOSITORY  lo pone GitHub Actions solo (usuario/repositorio)
"""
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("IG_TOKEN", "").strip()
PAT = os.environ.get("GH_PAT", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()


def refrescar():
    params = urllib.parse.urlencode({
        "grant_type": "ig_refresh_token",
        "access_token": TOKEN,
    })
    url = f"https://graph.instagram.com/refresh_access_token?{params}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode(errors="replace")
        cuerpo = cuerpo.replace(TOKEN, "[TOKEN OCULTO]") if TOKEN else cuerpo
        raise SystemExit(f"No se pudo renovar el token: {cuerpo}")


def guardar_en_secretos(nuevo):
    """Usa la CLI de GitHub para reescribir el secreto IG_TOKEN."""
    entorno = dict(os.environ, GH_TOKEN=PAT)
    subprocess.run(
        ["gh", "secret", "set", "IG_TOKEN", "--repo", REPO, "--body", nuevo],
        check=True, env=entorno,
    )


def main():
    if not TOKEN:
        raise SystemExit("Falta IG_TOKEN")

    r = refrescar()
    nuevo = r.get("access_token")
    dias = int(r.get("expires_in", 0)) // 86400

    if not nuevo:
        raise SystemExit("La respuesta no traia un token nuevo")

    print(f"Token renovado. Vence en {dias} dias.")

    if PAT and REPO:
        guardar_en_secretos(nuevo)
        print("Guardado automaticamente en los secretos del repositorio.")
    else:
        print("AVISO: no hay GH_PAT configurado, asi que el token nuevo NO se")
        print("guardo solo. Tienes que actualizarlo a mano en:")
        print(f"  https://github.com/{REPO or '<tu-repo>'}/settings/secrets/actions")
        print("Si no lo haces, la publicacion automatica se detendra cuando")
        print(f"venza el token actual (en unos {dias} dias).")


if __name__ == "__main__":
    main()
