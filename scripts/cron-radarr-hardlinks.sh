#!/bin/bash
# Cron script para sincronizar Radarr con los providers actuales.
# Ejecutar en el LXC de Radarr.
#
# Modos de uso:
#   cron-radarr-hardlinks.sh              → solo etiquetado (tag + clean via SSH)
#   cron-radarr-hardlinks.sh --hardlinks  → etiquetado + reconciliación de hardlinks
#
# Ejemplo de crontab:
#   0 3 * * * /usr/local/bin/cron-radarr-hardlinks.sh
#   0 5 * * * /usr/local/bin/cron-radarr-hardlinks.sh --hardlinks
#
# Configuración:
#   TAGARR_HOST       - usuario@host donde está instalado tagarr
#   SSH_KEY           - ruta a la clave SSH privada
#   TAGARR_VENV       - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   RADARR_URL        - URL de la API de Radarr
#   RADARR_API_KEY    - clave API de Radarr
#   NOT_AVAILABLE_TAG - etiqueta a excluir de los hardlinks (p. ej. no-streaming)
#   LOGFILE           - ruta al archivo de log (dejar vacío para desactivar)

TAGARR_HOST="${TAGARR_HOST:-user@host}"
SSH_KEY="${SSH_KEY:-/root/.ssh/tagarr_key}"
TAGARR_VENV="${TAGARR_VENV:-}"
RADARR_URL="${RADARR_URL:-http://localhost:7878}"
RADARR_API_KEY="${RADARR_API_KEY:-}"
NOT_AVAILABLE_TAG="${NOT_AVAILABLE_TAG:-no-streaming}"
LOGFILE="${LOGFILE:-/var/log/tagarr-cron-hardlinks.log}"

# Parse argumentos
HARDLINKS=false
for arg in "$@"; do
    case "$arg" in
        --hardlinks) HARDLINKS=true ;;
        *) echo "Uso: $(basename "$0") [--hardlinks]" >&2; exit 1 ;;
    esac
done

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    TAGARR_CMD="source $TAGARR_VENV/bin/activate && tagarr"
else
    TAGARR_CMD="tagarr"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

log "=== Inicio sincronización$([ "$HARDLINKS" = true ] && echo ' + hardlinks') ==="

# 1. Re-etiquetar toda la biblioteca via SSH
log "Re-etiquetando biblioteca..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
    "$TAGARR_CMD radarr tag" >> "${LOGFILE:-/dev/null}" 2>&1
log "Tagging exit code: $?"

# 2. Limpiar tags obsoletos via SSH
log "Limpiando tags obsoletos..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
    "$TAGARR_CMD radarr clean" >> "${LOGFILE:-/dev/null}" 2>&1
log "Clean exit code: $?"

if [ "$HARDLINKS" = false ]; then
    log "=== Sincronización completada ==="
    exit 0
fi

# 3. Obtener todos los tags de Radarr (id -> nombre)
all_tags=$(curl -s -H "X-Api-Key: $RADARR_API_KEY" "$RADARR_URL/api/v3/tag")

# 4. Obtener todas las películas
movies=$(curl -s -H "X-Api-Key: $RADARR_API_KEY" "$RADARR_URL/api/v3/movie")
movie_count=$(echo "$movies" | jq 'length')
log "Procesando $movie_count películas..."

echo "$movies" | jq -c '.[]' | while read -r movie; do
    movie_path=$(echo "$movie" | jq -r '.path')
    movie_rel_path=$(echo "$movie" | jq -r '.movieFile.relativePath // empty')

    # Saltar películas sin archivo descargado
    if [ -z "$movie_rel_path" ]; then
        continue
    fi

    movie_file="$movie_path/$movie_rel_path"
    tag_ids=$(echo "$movie" | jq -r '.tags[]? // empty')

    base_path=$(echo "$movie_path" | sed 's|/movies/.*||')
    movie_folder=$(basename "$movie_path")
    filename=$(basename "$movie_file")
    streaming_base="$base_path/streaming"

    # Construir lista de provider tags actuales
    current_providers=()
    for tag_id in $tag_ids; do
        tag_name=$(echo "$all_tags" | jq -r ".[] | select(.id == $tag_id) | .label")
        if [ -n "$tag_name" ] && [ "$tag_name" != "$NOT_AVAILABLE_TAG" ]; then
            current_providers+=("$tag_name")
        fi
    done

    # Añadir hardlinks faltantes
    for provider in "${current_providers[@]}"; do
        dest="$streaming_base/$provider/movies/$movie_folder/$filename"
        if [ ! -f "$dest" ]; then
            mkdir -p "$(dirname "$dest")"
            if ln "$movie_file" "$dest" 2>/dev/null; then
                log "Hardlink añadido: $dest"
            else
                log "Error al crear hardlink: $dest"
            fi
        fi
    done

    # Eliminar hardlinks obsoletos en carpetas de provider existentes
    if [ -d "$streaming_base" ]; then
        for provider_dir in "$streaming_base"/*/; do
            [ -d "$provider_dir" ] || continue
            provider=$(basename "$provider_dir")
            hardlink="$provider_dir/movies/$movie_folder/$filename"

            if [ -f "$hardlink" ]; then
                # Comprobar si este provider sigue siendo un tag actual
                found=false
                for p in "${current_providers[@]}"; do
                    [ "$p" = "$provider" ] && found=true && break
                done

                if [ "$found" = false ]; then
                    rm "$hardlink"
                    log "Hardlink obsoleto eliminado: $hardlink"

                    # Eliminar carpeta de película si quedó vacía
                    movie_dir="$provider_dir/movies/$movie_folder"
                    if [ -z "$(ls -A "$movie_dir" 2>/dev/null)" ]; then
                        rmdir "$movie_dir"
                        log "Carpeta vacía eliminada: $movie_dir"
                    fi
                fi
            fi
        done
    fi
done

log "=== Sincronización completada ==="
