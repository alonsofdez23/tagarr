#!/bin/bash
# Custom Script para Radarr (Settings > Connect > Custom Script)
# Ejecuta tagarr por SSH en el host donde está instalado.
# En el evento Download crea hardlinks en carpetas por proveedor de streaming.
#
# Configuración:
#   TAGARR_HOST       - usuario@host donde está instalado tagarr
#   SSH_KEY           - ruta a la clave SSH privada
#   TAGARR_VENV       - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   LOGFILE           - ruta al archivo de log (dejar vacío para desactivar)
#   RADARR_URL        - URL de la API de Radarr (para el evento Download)
#   RADARR_API_KEY    - clave API de Radarr (para el evento Download)
#   NOT_AVAILABLE_TAG - etiqueta a excluir de los hardlinks (p. ej. no-streaming)

TAGARR_HOST="${TAGARR_HOST:-user@host}"
SSH_KEY="${SSH_KEY:-/root/.ssh/tagarr_key}"
TAGARR_VENV="${TAGARR_VENV:-}"
LOGFILE="${LOGFILE:-/var/log/tagarr-radarr.log}"
RADARR_URL="${RADARR_URL:-http://localhost:7878}"
RADARR_API_KEY="${RADARR_API_KEY:-}"
NOT_AVAILABLE_TAG="${NOT_AVAILABLE_TAG:-no-streaming}"

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    TAGARR_CMD="source $TAGARR_VENV/bin/activate && tagarr"
else
    TAGARR_CMD="tagarr"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

create_hardlinks() {
    local movie_id="$1"
    local movie_path="$2"   # /mnt/arrstack/movies/Roofman (2025) [tmdbid-1242419]
    local file_path="$3"    # /mnt/arrstack/movies/Roofman (2025) [tmdbid-1242419]/Roofman.mkv

    # Extraer la ruta base (antes de /movies/)
    local base_path
    base_path=$(echo "$movie_path" | sed 's|/movies/.*||')
    # Resultado: /mnt/arrstack

    local movie_folder
    movie_folder=$(basename "$movie_path")
    # Resultado: Roofman (2025) [tmdbid-1242419]

    local filename
    filename=$(basename "$file_path")
    # Resultado: Roofman (2025) [tmdbid-1242419] - [WEBDL-1080p][EAC3 5.1][h265].mkv

    # Obtener las etiquetas actuales de la película desde la API de Radarr
    local tag_ids
    tag_ids=$(curl -s -H "X-Api-Key: $RADARR_API_KEY" "$RADARR_URL/api/v3/movie/$movie_id" \
        | jq -r '.tags[]? // empty')

    if [ -z "$tag_ids" ]; then
        log "La película no tiene etiquetas, no se crean hardlinks"
        return
    fi

    # Obtener todos los tags para mapear ID -> nombre
    local all_tags
    all_tags=$(curl -s -H "X-Api-Key: $RADARR_API_KEY" "$RADARR_URL/api/v3/tag")

    local hardlinks_created=0
    for tag_id in $tag_ids; do
        local tag_name
        tag_name=$(echo "$all_tags" | jq -r ".[] | select(.id == $tag_id) | .label")

        # Saltar tags vacíos o el not_available_tag
        if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
            log "Etiqueta '$tag_name' omitida (not_available_tag)"
            continue
        fi

        # /mnt/arrstack/streaming/netflix/movies/Roofman (2025) [tmdbid-1242419]/
        local dest_dir="$base_path/streaming/$tag_name/movies/$movie_folder"
        mkdir -p "$dest_dir"

        if ln "$file_path" "$dest_dir/$filename" 2>/dev/null; then
            log "Hardlink creado: $dest_dir/$filename"
            hardlinks_created=$((hardlinks_created + 1))
        else
            log "Error al crear hardlink: $dest_dir/$filename"
        fi
    done

    if [ "$hardlinks_created" -eq 0 ]; then
        log "No hay providers de streaming, no se crean hardlinks"
    fi
}

delete_hardlinks() {
    local movie_path="$1"   # /mnt/arrstack/movies/The Batman (2022) [tmdbid-414906]
    local file_path="$2"    # /mnt/arrstack/movies/The Batman (2022) [...].mkv
    local movie_tags="$3"   # amazon-prime-video|hbo-max|netflix (separados por |)

    local base_path
    base_path=$(echo "$movie_path" | sed 's|/movies/.*||')

    local movie_folder
    movie_folder=$(basename "$movie_path")

    local filename
    filename=$(basename "$file_path")

    if [ -z "$movie_tags" ]; then
        log "La película no tiene etiquetas, no hay hardlinks que eliminar"
        return
    fi

    IFS='|' read -ra tags <<< "$movie_tags"
    for tag_name in "${tags[@]}"; do
        if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
            continue
        fi

        local hardlink="$base_path/streaming/$tag_name/movies/$movie_folder/$filename"

        if [ -f "$hardlink" ]; then
            rm "$hardlink"
            log "Hardlink eliminado: $hardlink"

            # Eliminar la carpeta de la película si quedó vacía
            local movie_dir="$base_path/streaming/$tag_name/movies/$movie_folder"
            if [ -z "$(ls -A "$movie_dir" 2>/dev/null)" ]; then
                rmdir "$movie_dir"
                log "Carpeta vacía eliminada: $movie_dir"
            fi
        else
            log "Hardlink no encontrado: $hardlink"
        fi
    done
}

case "$radarr_eventtype" in
    MovieAdded)
        log "Event: $radarr_eventtype | Movie ID: $radarr_movie_id"
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
            "$TAGARR_CMD radarr tag --id $radarr_movie_id" >> "${LOGFILE:-/dev/null}" 2>&1
        log "Exit code: $?"
        ;;
    Download)
        log "Event: $radarr_eventtype | Movie ID: $radarr_movie_id | File: $radarr_moviefile_path"
        # Re-etiquetar por si los providers cambiaron desde MovieAdded
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
            "$TAGARR_CMD radarr tag --id $radarr_movie_id" >> "${LOGFILE:-/dev/null}" 2>&1
        log "Tagging exit code: $?"
        # Crear hardlinks en carpetas de proveedor
        create_hardlinks "$radarr_movie_id" "$radarr_movie_path" "$radarr_moviefile_path"
        ;;
    MovieFileDelete)
        log "Event: $radarr_eventtype | Movie ID: $radarr_movie_id | File: $radarr_moviefile_path"
        delete_hardlinks "$radarr_movie_path" "$radarr_moviefile_path" "$radarr_movie_tags"
        ;;
    MovieDelete)
        if [ "$radarr_movie_deletedfiles" = "True" ]; then
            log "Event: $radarr_eventtype | Movie ID: $radarr_movie_id | DeletedFiles: True"
            base_path=$(echo "$radarr_movie_path" | sed 's|/movies/.*||')
            movie_folder=$(basename "$radarr_movie_path")

            IFS='|' read -ra tags <<< "$radarr_movie_tags"
            for tag_name in "${tags[@]}"; do
                if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
                    continue
                fi

                movie_dir="$base_path/streaming/$tag_name/movies/$movie_folder"
                if [ -d "$movie_dir" ]; then
                    rm -rf "$movie_dir"
                    log "Carpeta eliminada: $movie_dir"
                else
                    log "Carpeta no encontrada: $movie_dir"
                fi
            done
        fi
        ;;
    Test)
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" "echo 'Tagarr Radarr: test OK'"
        ;;
esac
