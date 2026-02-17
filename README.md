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

# Modo depuración
tagarr --debug radarr tag --progress
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
