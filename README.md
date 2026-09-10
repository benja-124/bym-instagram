# ByM Solutions — publicación automática en Instagram

Publica solo, en las fechas que tú definas, sin abrir Canva ni entrar a Instagram.

## Cómo funciona

Tú escribes el texto de cada publicación en `calendario.json`. De ahí en adelante todo es automático: un proceso genera la gráfica con la marca aplicada, otro la publica el día que corresponde, y un tercero renueva el token antes de que venza.

```
calendario.json ──► generar.py ──► imagenes/*.png ──► GitHub Pages (URL pública)
                                                              │
                                    publicar.py ◄─────────────┘
                                          │
                                    API de Instagram
```

El detalle importante: la API de Instagram **no acepta que le subas un archivo**, exige una URL pública. Por eso las imágenes se guardan en el repositorio y se sirven por GitHub Pages. Y como la API **tampoco programa a futuro**, el que decide cuándo publicar es el cron de GitHub Actions.

## Puesta en marcha (una sola vez)

### 1. Crear el repositorio

Sube estos archivos a un repositorio **público** de GitHub. Tiene que ser público para que GitHub Pages funcione gratis y para que Instagram pueda leer las imágenes. No hay riesgo: el token no vive acá, vive en los secretos, que van cifrados y no se ven ni siendo público el repositorio.

### 2. Activar GitHub Pages

En **Settings → Pages**, en "Source" elige la rama `main` y la carpeta `/ (root)`. Guarda. GitHub te va a mostrar una dirección del tipo:

```
https://TU-USUARIO.github.io/NOMBRE-DEL-REPO/
```

Anótala, la necesitas en el paso siguiente.

### 3. Cargar los secretos

En **Settings → Secrets and variables → Actions → New repository secret**, crea estos tres:

| Secreto | Valor |
|---|---|
| `IG_TOKEN` | El token de acceso de Instagram (ver más abajo) |
| `IG_USER_ID` | `17841435918607928` |
| `BASE_URL` | La dirección de GitHub Pages del paso 2, sin la barra final |

**Sobre el token:** genéralo de nuevo desde Meta (panel de la app → API de Instagram → *Generar tokens de acceso* → **Genera**) y pégalo directo acá. No lo mandes por chat, correo ni WhatsApp. Generar uno nuevo invalida el anterior automáticamente, así que si alguna vez uno se expone, la solución es simplemente generar otro.

### 4. Opcional pero recomendado: renovación sin intervención

El token de Instagram dura 60 días. El proceso `renovar-token.yml` lo renueva cada mes, pero para que pueda **guardar** el token nuevo necesita permiso de escritura sobre los secretos.

Crea un token personal de GitHub (**Settings de tu cuenta → Developer settings → Personal access tokens → Fine-grained**), dale acceso solo a este repositorio con el permiso **Secrets: Read and write**, y guárdalo como el secreto `GH_PAT`.

Si no haces esto, todo sigue funcionando igual, pero cada dos meses vas a tener que pegar un token nuevo a mano. El proceso te avisa en el registro cuántos días quedan.

### 5. Generar las imágenes

Ve a la pestaña **Actions → Generar imágenes → Run workflow**. Eso crea los PNG y los sube al repositorio. Desde ese momento quedan disponibles en la URL pública.

### 6. Probar antes de confiar

En **Actions → Publicar en Instagram → Run workflow**, ejecútalo a mano. Si la fecha de hoy coincide con algún post del calendario, lo va a publicar de verdad. Si no coincide, te dirá "No hay nada programado para hoy" — que también sirve para confirmar que el token y los permisos están bien.

Para una prueba real, cambia la fecha de un post a la de hoy en `calendario.json`, ejecuta, y revisa el perfil.

## Uso diario

Editas `calendario.json` y listo. Cada entrada necesita:

```json
{
  "id": "post-04",
  "fecha": "2026-09-21",
  "publicado": false,
  "plantilla": "declaracion",
  "kicker": "Texto chico de arriba",
  "titulo": "El titular grande",
  "bajada": "La frase de apoyo",
  "texto": "El caption completo que va en Instagram, con emojis y hashtags."
}
```

Al guardar el cambio, las imágenes se regeneran solas. El día indicado se publica solo.

### Las tres plantillas

- **`declaracion`** — fondo ámbar, titular grande. Para afirmaciones y llamados a la acción. Usa `titulo` y `bajada`.
- **`lista`** — fondo azul con tarjetas blancas numeradas. Para contenido educativo. Usa `titulo` e `items` (una lista de frases).
- **`pasos`** — bloque ámbar arriba, pasos abajo. Para explicar cómo funciona algo. Usa `titulo` y `pasos` (lista de pares `["1", "texto"]`).

## Límites que conviene saber

Instagram permite **25 publicaciones por día**, así que publicando tres veces por semana sobra. El cron de GitHub **puede atrasarse entre 5 y 30 minutos** cuando la plataforma está cargada; para redes sociales no importa. Las **historias no se publican de forma confiable por API**, así que esas quedan manuales. Y GitHub desactiva los procesos programados si el repositorio pasa **60 días sin actividad** — como el propio proceso hace cambios cada vez que publica, eso se resuelve solo mientras esté funcionando.

## Costo

Cero. GitHub Actions y Pages son gratis en repositorios públicos, y la API de Instagram no cobra por publicar.
