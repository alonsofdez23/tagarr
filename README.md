# Tagarr

Tagarr es una herramienta CLI que interactúa con instancias de Radarr y Sonarr. Detecta películas y series disponibles en los proveedores de streaming configurados (a través de JustWatch) y **añade etiquetas** en Radarr/Sonarr con el nombre del proveedor (p. ej. `netflix`, `amazon-prime-video`, `disney-plus`). También puede **limpiar etiquetas obsoletas** cuando el contenido ya no está disponible en un proveedor.

> Basado en [Excludarr](https://github.com/haijeploeg/excludarr) de Haije Ploeg. En lugar de eliminar o deshabilitar el seguimiento, Tagarr se centra en etiquetar tu biblioteca con información de proveedores de streaming.

## Cómo funciona

1. Tagarr consulta la API GraphQL de JustWatch para averiguar qué proveedores de streaming configurados ofrecen cada película/serie.
2. Para cada coincidencia, crea una etiqueta en Radarr/Sonarr con el nombre del proveedor sanitizado (solo `a-z`, `0-9` y `-`). Por ejemplo: `netflix`, `amazon-prime-video`, `disney-plus`.
3. Las etiquetas se añaden al objeto de la película/serie para que puedas filtrar tu biblioteca por proveedor de streaming en la interfaz de Radarr/Sonarr.
4. El comando `clean` elimina las etiquetas de los títulos que **ya no están disponibles** en un proveedor.

## Requisitos previos

- Python 3.8+ o Docker
- Radarr V3+
- Sonarr V3+ (V2 no está soportado)

## Instalación

```bash
git clone <repo-url>
cd tagarr
pip install -e .
```

> **Nota:** Si tu sistema no permite instalar paquetes Python globalmente (error `externally-managed-environment`), crea un entorno virtual primero:
>
> ```bash
> python3 -m venv venv
> source venv/bin/activate
> pip install -e .
> ```
>
> Cada vez que abras una terminal nueva, activa el entorno con `source venv/bin/activate` antes de usar Tagarr.

## Configuración

Crea un archivo de configuración en una de las siguientes ubicaciones (en orden de prioridad, el último tiene preferencia):

```
/etc/tagarr/tagarr.yml
~/.config/tagarr/tagarr.yml
~/.tagarr/config/tagarr.yml
~/.tagarr.yml
./.tagarr.yml
```

### Ejemplo de configuración

```yaml
general:
  fast_search: true
  locale: es_ES
  # Opcional: etiqueta para contenido no disponible en ningún proveedor
  # not_available_tag: no-streaming
  providers:
    - Netflix
    - Amazon Prime Video
    - Disney Plus

# Opcional: TMDB como alternativa para series no encontradas por IMDB ID
tmdb:
  api_key: YOUR_TMDB_API_KEY

radarr:
  url: 'http://localhost:7878'
  api_key: YOUR_RADARR_API_KEY
  verify_ssl: false
  # Opcional: títulos a omitir durante el etiquetado/limpieza
  exclude:
    # - 'Alguna Película'

sonarr:
  url: 'http://localhost:8989'
  api_key: YOUR_SONARR_API_KEY
  verify_ssl: false
  exclude:
    # - 'Alguna Serie'
```

> Para obtener la lista completa de proveedores disponibles en tu país, ejecuta `tagarr providers list`.

## Uso

### Proveedores

Lista todos los proveedores de streaming disponibles para tu localización:

```bash
tagarr providers list
tagarr providers list -l en_US
```

### Radarr

#### Etiquetar películas

Detecta películas disponibles en los proveedores de streaming configurados y añade etiquetas en Radarr:

```bash
tagarr radarr tag --progress
```

Ejemplo de salida:

```
                                                  ╷
 Title                                            │ Providers Tagged
╶─────────────────────────────────────────────────┼────────────────────────────╴
 El señor de los anillos: La comunidad del anillo │ netflix, amazon-prime-video
 Lilo y Stitch                                    │ disney-plus
 The Batman                                       │ netflix, amazon-prime-video
                                                  ╵

Successfully tagged 3 movies in Radarr!
```

Después de ejecutar este comando, puedes ir a Radarr y filtrar tu biblioteca por etiquetas como `netflix`, `disney-plus`, etc.

#### Etiquetar contenido no disponible

Si configuras `not_available_tag` en la sección `general`, las películas que **no estén disponibles en ningún proveedor** recibirán esa etiqueta. Esto permite filtrar en Radarr el contenido que no está en ninguna plataforma de streaming:

```yaml
general:
  not_available_tag: no-streaming
```

```bash
tagarr radarr tag --progress
```

Ejemplo de salida:

```
                                                  ╷
 Title                                            │ Providers Tagged
╶─────────────────────────────────────────────────┼────────────────────────────╴
 El señor de los anillos: La comunidad del anillo │ netflix, amazon-prime-video
 Inception                                        │ no-streaming
                                                  ╵
```

El comando `clean` eliminará automáticamente la etiqueta `no-streaming` de las películas que **ahora sí tienen proveedores**.

#### Limpiar etiquetas obsoletas

Elimina las etiquetas de proveedores de streaming de películas que ya no están disponibles en esos proveedores:

```bash
tagarr radarr clean --progress
```

Ejemplo de salida:

```
       ╷
 Title │ Tags Removed
╶──────┼──────────────────╴
 F9    │ disney-plus
       ╵

Successfully cleaned tags from 1 movies in Radarr!
```

#### Purgar una etiqueta

Elimina una etiqueta concreta de **todas** las películas en Radarr. Útil para eliminar por completo la etiqueta `no-streaming` si decides dejar de usar la funcionalidad:

```bash
# Usa not_available_tag del config por defecto
tagarr radarr purge-tag

# O especifica una etiqueta concreta
tagarr radarr purge-tag --tag no-streaming
```

### Sonarr

#### Etiquetar series

Detecta series disponibles en los proveedores de streaming configurados y añade etiquetas en Sonarr. Las etiquetas se aplican a nivel de **serie**, agregando todos los proveedores encontrados en todos los episodios:

```bash
tagarr sonarr tag --progress
```

#### Limpiar etiquetas obsoletas

Elimina las etiquetas de proveedores de streaming de series que ya no están disponibles en esos proveedores:

```bash
tagarr sonarr clean --progress
```

#### Purgar una etiqueta

Elimina una etiqueta concreta de **todas** las series en Sonarr:

```bash
tagarr sonarr purge-tag
tagarr sonarr purge-tag --tag no-streaming
```

### Opciones CLI

Los comandos `tag` y `clean` soportan estas opciones:

Opción | Corto | Descripción
--- | --- | ---
`--provider` | `-p` | Sobrescribe los proveedores de streaming configurados (se puede especificar varias veces)
`--locale` | `-l` | Sobrescribe la localización configurada (p. ej. `en_US`, `es_ES`)
`--progress` | | Muestra una barra de progreso durante el procesamiento
`--id` | | ID de Radarr/Sonarr de un elemento concreto a procesar (en lugar de toda la biblioteca)

El comando `purge-tag` soporta:

Opción | Corto | Descripción
--- | --- | ---
`--tag` | `-t` | Etiqueta a eliminar. Por defecto usa `not_available_tag` del config

Opciones globales:

Opción | Descripción
--- | ---
`--debug` | Activa el registro de depuración
`--version` | Muestra la versión y sale

### Ejemplos

```bash
# Etiquetar películas con barra de progreso
tagarr radarr tag --progress

# Etiquetar series usando proveedores específicos
tagarr sonarr tag -p Netflix -p "Disney Plus" --progress

# Limpiar etiquetas obsoletas con una localización diferente
tagarr radarr clean -l en_US --progress

# Eliminar la etiqueta "no-streaming" de todas las películas
tagarr radarr purge-tag --tag no-streaming

# Eliminar la etiqueta not_available_tag (del config) de todas las series
tagarr sonarr purge-tag

# Etiquetar solo una película por su ID de Radarr
tagarr radarr tag --id 67

# Limpiar etiquetas de una serie por su ID de Sonarr
tagarr sonarr clean --id 15

# Modo depuración
tagarr --debug radarr tag --progress
```

### Integración con Custom Scripts de Radarr/Sonarr

Puedes usar la opción `--id` junto con los Custom Scripts de Radarr/Sonarr para etiquetar automáticamente películas y series cuando se añaden o descargan. En lugar de recorrer toda la biblioteca, Tagarr solo procesa el elemento afectado por el evento.

El repositorio incluye scripts listos para usar en la carpeta `scripts/`:

- `scripts/tagarr-radarr.sh` — Custom Script para Radarr
- `scripts/tagarr-sonarr.sh` — Custom Script para Sonarr

#### Cómo funcionan

Radarr y Sonarr permiten ejecutar scripts personalizados en respuesta a eventos (Settings > Connect > Custom Script). Cuando ocurre un evento, pasan el ID del elemento como variable de entorno (`radarr_movie_id` / `sonarr_series_id`). Los scripts de Tagarr usan ese ID con la opción `--id` para etiquetar solo ese elemento.

Los scripts se conectan por **SSH** al host donde está instalado Tagarr, lo que permite usarlos cuando Radarr/Sonarr se ejecutan en máquinas o contenedores diferentes (p. ej. LXC de Proxmox).

##### Eventos y acciones

El script de Radarr (`tagarr-radarr.sh`) responde a dos eventos:

| Evento | Trigger en Radarr | Acción |
| --- | --- | --- |
| `MovieAdded` | On Movie Added | Etiqueta la película con sus proveedores de streaming |
| `Download` | On Download | Re-etiqueta la película y crea **hardlinks** en carpetas por proveedor |

El script de Sonarr (`tagarr-sonarr.sh`) solo responde al evento `SeriesAdd` (On Series Add) para etiquetar la serie.

##### Hardlinks por proveedor (solo Radarr)

En el evento `Download`, el script crea automáticamente hardlinks del archivo descargado en carpetas nombradas según el proveedor de streaming. La estructura resultante es:

```
/mnt/arrstack/streaming/
├── netflix/
│   └── movies/
│       └── Película (2025) [tmdbid-123]/
│           └── Película (2025).mkv  → hardlink
└── amazon-prime-video/
    └── movies/
        └── Película (2025) [tmdbid-123]/
            └── Película (2025).mkv  → hardlink
```

La ruta base (`/mnt/arrstack/`) se extrae automáticamente de la ruta de la película. Los hardlinks solo se crean si la película está disponible en al menos un proveedor — si solo tiene la etiqueta `not_available_tag` no se crea ningún hardlink.

> **Nota:** Los hardlinks requieren que la carpeta `streaming/` esté en el mismo sistema de archivos que la biblioteca de películas. Si Radarr escanea esa carpeta, añádela a la lista de carpetas excluidas en Settings > Media Management.

#### Configuración

Los scripts se configuran editando directamente las variables al inicio del script:

**`tagarr-radarr.sh`**

Variable | Por defecto | Descripción
--- | --- | ---
`TAGARR_HOST` | `user@host` | Usuario y dirección del host donde está instalado Tagarr
`SSH_KEY` | `/root/.ssh/tagarr_key` | Ruta a la clave SSH privada
`TAGARR_VENV` | *(vacío)* | Ruta al virtualenv de Tagarr (dejar vacío si está instalado globalmente)
`LOGFILE` | `/var/log/tagarr-radarr.log` | Ruta al archivo de log (dejar vacío para desactivar)
`RADARR_URL` | `http://localhost:7878` | URL de la API de Radarr (para el evento Download)
`RADARR_API_KEY` | *(vacío)* | Clave API de Radarr (necesaria para el evento Download)
`NOT_AVAILABLE_TAG` | `no-streaming` | Etiqueta a excluir de los hardlinks

**`tagarr-sonarr.sh`**

Variable | Por defecto | Descripción
--- | --- | ---
`TAGARR_HOST` | `user@host` | Usuario y dirección del host donde está instalado Tagarr
`SSH_KEY` | `/root/.ssh/tagarr_key` | Ruta a la clave SSH privada
`TAGARR_VENV` | *(vacío)* | Ruta al virtualenv de Tagarr (dejar vacío si está instalado globalmente)
`LOGFILE` | `/var/log/tagarr-sonarr.log` | Ruta al archivo de log (dejar vacío para desactivar)

#### Instalación paso a paso

1. **Genera una clave SSH** en la máquina donde corre Radarr/Sonarr y cópiala al host de Tagarr:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/tagarr_key -N ""
ssh-copy-id -i /root/.ssh/tagarr_key usuario@host-tagarr
```

2. **Copia el script** correspondiente a la máquina de Radarr/Sonarr:

```bash
scp scripts/tagarr-radarr.sh root@host-radarr:/usr/local/bin/tagarr-radarr.sh
scp scripts/tagarr-sonarr.sh root@host-sonarr:/usr/local/bin/tagarr-sonarr.sh
```

3. **Edita las variables** en cada script con tus valores:

```bash
TAGARR_HOST="${TAGARR_HOST:-usuario@192.168.1.100}"
TAGARR_VENV="${TAGARR_VENV:-/home/usuario/tagarr/venv}"
RADARR_API_KEY="${RADARR_API_KEY:-tu_api_key}"  # Solo en tagarr-radarr.sh
```

4. **Configura el Custom Script** en Radarr/Sonarr:
   - Ve a Settings > Connect > + > Custom Script
   - Path: `/usr/local/bin/tagarr-radarr.sh` (o `tagarr-sonarr.sh`)
   - Triggers Radarr: marca **"On Movie Added"** y **"On Download"**
   - Triggers Sonarr: marca **"On Series Add"**
   - Pulsa "Test" para verificar la conexión SSH

#### Verificación

Los scripts escriben un log con cada ejecución. Para comprobar que funcionan:

```bash
# En la máquina de Radarr
cat /var/log/tagarr-radarr.log

# En la máquina de Sonarr
cat /var/log/tagarr-sonarr.log
```

Ejemplo de salida para una película disponible en Netflix:

```
[Thu Feb 19 16:09:12 CET 2026] Event: Download | Movie ID: 42 | File: /mnt/arrstack/movies/...
Successfully tagged 1 movies in Radarr!
[Thu Feb 19 16:09:13 CET 2026] Tagging exit code: 0
[Thu Feb 19 16:09:13 CET 2026] Hardlink creado: /mnt/arrstack/streaming/netflix/movies/Película (2025) [...]/Película.mkv
```

Ejemplo para una película sin proveedores:

```
[Thu Feb 19 16:09:12 CET 2026] Event: Download | Movie ID: 82 | File: /mnt/arrstack/movies/...
Successfully tagged 1 movies in Radarr!
[Thu Feb 19 16:09:13 CET 2026] Tagging exit code: 0
[Thu Feb 19 16:09:13 CET 2026] Etiqueta 'no-streaming' omitida (not_available_tag)
[Thu Feb 19 16:09:13 CET 2026] No hay providers de streaming, no se crean hardlinks
```

> **Nota:** Asegúrate de que el archivo de configuración de Tagarr (`tagarr.yml`) esté en una ruta global como `~/.config/tagarr/tagarr.yml` en el host de Tagarr, ya que los scripts se ejecutan por SSH y no necesariamente desde el directorio del proyecto.

### Ejecución programada con cron

Los Custom Scripts solo etiquetan elementos nuevos cuando se añaden. Para mantener las etiquetas actualizadas (detectar cambios de proveedor y limpiar etiquetas obsoletas), es recomendable ejecutar Tagarr periódicamente sobre toda la biblioteca.

El repositorio incluye scripts de cron listos para usar:

- `scripts/cron-radarr.sh` — Ejecuta `tag` + `clean` para toda la biblioteca de Radarr
- `scripts/cron-sonarr.sh` — Ejecuta `tag` + `clean` para toda la biblioteca de Sonarr

#### Configuración

Los scripts se configuran con las siguientes variables de entorno (también se pueden editar directamente en el script):

Variable | Por defecto | Descripción
--- | --- | ---
`TAGARR_VENV` | *(vacío)* | Ruta al virtualenv de Tagarr (dejar vacío si está instalado globalmente)
`LOGFILE` | `~/.local/log/tagarr-cron-radarr.log` o `~/.local/log/tagarr-cron-sonarr.log` | Ruta al archivo de log (dejar vacío para desactivar)

#### Instalación

Añade las entradas al crontab del host donde está instalado Tagarr:

```bash
crontab -e
```

```bash
# Radarr: cada día a las 3:00
0 3 * * * TAGARR_VENV=/ruta/al/venv /ruta/a/scripts/cron-radarr.sh

# Sonarr: cada día a las 4:00
0 4 * * * TAGARR_VENV=/ruta/al/venv /ruta/a/scripts/cron-sonarr.sh
```

#### Verificación

```bash
cat ~/.local/log/tagarr-cron-radarr.log
cat ~/.local/log/tagarr-cron-sonarr.log
```

Ejemplo de salida:

```
[Mon Feb 17 03:00:01 UTC 2026] Inicio: tagarr radarr tag
Successfully tagged 5 movies in Radarr!
[Mon Feb 17 03:01:30 UTC 2026] Exit code: 0
[Mon Feb 17 03:01:30 UTC 2026] Inicio: tagarr radarr clean
Successfully cleaned tags from 2 movies in Radarr!
[Mon Feb 17 03:02:45 UTC 2026] Exit code: 0
```

## Docker

Puedes usar las siguientes variables de entorno:

Variable | Por defecto | Descripción
--- | --- | ---
GENERAL_FAST_SEARCH | true | Activa o desactiva la búsqueda rápida, puede ser `true` o `false`
GENERAL_LOCALE | en_US | La localización a usar, también puede ser un código de país de dos letras
GENERAL_PROVIDERS | netflix | Lista de proveedores separados por comas, p. ej. `netflix, amazon prime video`
GENERAL_NOT_AVAILABLE_TAG | - | Etiqueta para contenido no disponible en ningún proveedor (p. ej. `no-streaming`)
TMDB_API_KEY | - | Tu clave API de TMDB (opcional, se usa como alternativa para buscar series)
RADARR_URL | http://localhost:7878 | La URL de Radarr
RADARR_API_KEY | secret | Tu clave API de Radarr
RADARR_VERIFY_SSL | false | Activa la verificación SSL
RADARR_EXCLUDE | - | Lista de títulos de películas a omitir, separados por comas
SONARR_URL | http://localhost:8989 | La URL de Sonarr
SONARR_API_KEY | secret | Tu clave API de Sonarr
SONARR_VERIFY_SSL | false | Activa la verificación SSL
SONARR_EXCLUDE | - | Lista de títulos de series a omitir, separados por comas
CRON_MODE | false | Ejecuta el contenedor en modo cron

### Docker run

```bash
docker run -it --rm --env-file tagarr.env tagarr:latest radarr tag --progress
docker run -it --rm --env-file tagarr.env tagarr:latest sonarr tag --progress
docker run -it --rm --env-file tagarr.env tagarr:latest radarr clean --progress
```

### Docker Compose con cron

Tagarr puede ejecutarse de forma programada usando el modo cron. Crea un archivo crontab y móntalo:

```bash
# crontab
# minuto    hora    día   mes   día_semana   comando
0           1       *     *     *            tagarr radarr tag --progress
0           2       *     *     *            tagarr sonarr tag --progress
0           3       *     *     *            tagarr radarr clean --progress
0           4       *     *     *            tagarr sonarr clean --progress
```

```yaml
# docker-compose.yml
version: "3"
services:
  tagarr:
    image: tagarr
    container_name: tagarr
    environment:
      - GENERAL_FAST_SEARCH=true
      - GENERAL_LOCALE=es_ES
      - GENERAL_PROVIDERS=netflix, amazon prime video, disney plus
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=your_api_key
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=your_api_key
      - CRON_MODE=true
    volumes:
      - ./crontab:/etc/tagarr/crontab
    restart: unless-stopped
```

## Preguntas frecuentes

**P:** ¿Qué formato tienen las etiquetas?

**R:** Las etiquetas se crean usando el nombre del proveedor en minúsculas, reemplazando espacios y caracteres especiales por guiones. Por ejemplo: `netflix`, `amazon-prime-video`, `disney-plus`, `hbo-max`. Esto cumple con las restricciones de Radarr/Sonarr que solo permiten caracteres `a-z`, `0-9` y `-` en etiquetas.

---

**P:** ¿Tagarr elimina o deshabilita el seguimiento de algún contenido?

**R:** No. Tagarr **solo añade y elimina etiquetas**. Nunca borra películas/series ni cambia su estado de seguimiento.

---

**P:** ¿Cómo funciona el comando `clean`?

**R:** Encuentra películas/series que tienen etiquetas de proveedores de streaming pero que **ya no están disponibles** en esos proveedores según JustWatch, y elimina solo las etiquetas obsoletas.

---

**P:** ¿Puedo excluir títulos del procesamiento?

**R:** Sí, usa la lista `exclude` en tu archivo de configuración dentro de la sección `radarr` o `sonarr`.

---

**P:** ¿Cómo sé qué proveedores están disponibles?

**R:** Ejecuta `tagarr providers list` para ver todos los proveedores disponibles para tu localización configurada.

---

**P:** ¿Las etiquetas se aplican por episodio o por serie en Sonarr?

**R:** Las etiquetas en Sonarr se aplican a nivel de **serie**. Tagarr revisa todos los episodios de todas las temporadas y agrega los proveedores encontrados, luego etiqueta la serie con todos ellos.

---

**P:** ¿Qué es `not_available_tag`?

**R:** Es una opción que permite etiquetar las películas/series que **no están disponibles en ninguno** de los proveedores configurados. Por ejemplo, con `not_available_tag: no-streaming`, todo el contenido sin proveedor recibirá la etiqueta `no-streaming`. El comando `clean` la eliminará automáticamente si el contenido vuelve a estar disponible. Si quieres eliminar la etiqueta de todo de golpe, usa `tagarr radarr purge-tag` o `tagarr sonarr purge-tag`.

---

**P:** ¿Tagarr soporta Sonarr V2?

**R:** No. Sonarr V2 ha llegado al fin de su vida útil. Por favor, actualiza a Sonarr V3+.
