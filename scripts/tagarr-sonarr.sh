#!/bin/bash
# Custom Script para Sonarr (Settings > Connect > Custom Script)
# Ejecuta tagarr por SSH en el host donde está instalado.
# En el evento Download crea hardlinks en carpetas por proveedor de streaming.
#
# Configuración:
#   TAGARR_HOST       - usuario@host donde está instalado tagarr
#   SSH_KEY           - ruta a la clave SSH privada
#   TAGARR_VENV       - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   LOGFILE           - ruta al archivo de log (dejar vacío para desactivar)
#   SONARR_URL        - URL de la API de Sonarr (para el evento Download)
#   SONARR_API_KEY    - clave API de Sonarr (para el evento Download)
#   NOT_AVAILABLE_TAG - etiqueta a excluir de los hardlinks (p. ej. no-streaming)

TAGARR_HOST="${TAGARR_HOST:-user@host}"
SSH_KEY="${SSH_KEY:-/root/.ssh/tagarr_key}"
TAGARR_VENV="${TAGARR_VENV:-}"
LOGFILE="${LOGFILE:-/var/log/tagarr-sonarr.log}"
SONARR_URL="${SONARR_URL:-http://localhost:8989}"
SONARR_API_KEY="${SONARR_API_KEY:-}"
NOT_AVAILABLE_TAG="${NOT_AVAILABLE_TAG:-no-streaming}"
# Activar hardlinks: crea/elimina hardlinks por proveedor en eventos Download/Delete
ENABLE_HARDLINKS=true

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    TAGARR_CMD="source $TAGARR_VENV/bin/activate && tagarr"
else
    TAGARR_CMD="tagarr"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

# Extrae componentes de la ruta de la serie:
#   sonarr_series_path = /mnt/arrstack/tvseries/Fallout (2024) [tvdbid-416744]
#   → base_path   = /mnt/arrstack
#   → series_type = tvseries  (o anime, según la carpeta raíz de Sonarr)
#   → series_folder = Fallout (2024) [tvdbid-416744]
parse_series_path() {
    series_root=$(dirname "$sonarr_series_path")   # /mnt/arrstack/tvseries
    base_path=$(dirname "$series_root")             # /mnt/arrstack
    series_type=$(basename "$series_root")          # tvseries o anime
    series_folder=$(basename "$sonarr_series_path") # Fallout (2024) [tvdbid-416744]
}

create_hardlinks() {
    local file_path="$1"    # /mnt/arrstack/tvseries/Fallout.../Season 01/episodio.mkv
    local series_tags="$2"  # amazon-prime-video|netflix (separados por |)

    parse_series_path

    # Ruta relativa del episodio dentro de la carpeta de la serie
    # e.g.: Season 01/Fallout S01E01.mkv
    # Usar longitud para evitar interpretación glob de los corchetes en el nombre de la serie
    local episode_rel_path="${file_path:${#sonarr_series_path}+1}"

    if [ -z "$series_tags" ]; then
        log "La serie no tiene etiquetas, no se crean hardlinks"
        return
    fi

    local hardlinks_created=0
    IFS='|' read -ra tags <<< "$series_tags"
    for tag_name in "${tags[@]}"; do
        if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
            log "Etiqueta '$tag_name' omitida (not_available_tag)"
            continue
        fi

        # /mnt/arrstack/streaming/netflix/tvseries/Fallout (2024) [...]/Season 01/
        local dest="$base_path/streaming/$tag_name/$series_type/$series_folder/$episode_rel_path"
        mkdir -p "$(dirname "$dest")"

        if ln "$file_path" "$dest" 2>/dev/null; then
            log "Hardlink creado: $dest"
            hardlinks_created=$((hardlinks_created + 1))
        else
            log "Error al crear hardlink: $dest"
        fi
    done

    if [ "$hardlinks_created" -eq 0 ]; then
        log "No hay providers de streaming, no se crean hardlinks"
    fi
}

delete_episode_hardlinks() {
    local file_path="$1"    # /mnt/arrstack/tvseries/Fallout.../Season 01/episodio.mkv
    local series_tags="$2"  # amazon-prime-video|netflix (separados por |)

    parse_series_path

    local episode_rel_path="${file_path:${#sonarr_series_path}+1}"
    local episode_dir=$(dirname "$episode_rel_path")  # Season 01

    IFS='|' read -ra tags <<< "$series_tags"
    for tag_name in "${tags[@]}"; do
        if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
            continue
        fi

        local hardlink="$base_path/streaming/$tag_name/$series_type/$series_folder/$episode_rel_path"

        if [ -f "$hardlink" ]; then
            rm "$hardlink"
            log "Hardlink eliminado: $hardlink"

            # Eliminar carpeta de temporada si quedó vacía
            local season_dir="$base_path/streaming/$tag_name/$series_type/$series_folder/$episode_dir"
            if [ -z "$(ls -A "$season_dir" 2>/dev/null)" ]; then
                rmdir "$season_dir"
                log "Carpeta vacía eliminada: $season_dir"
            fi
        else
            log "Hardlink no encontrado: $hardlink"
        fi
    done
}

case "$sonarr_eventtype" in
    SeriesAdd)
        log "Event: $sonarr_eventtype | Series ID: $sonarr_series_id"
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
            "$TAGARR_CMD sonarr tag --id $sonarr_series_id" >> "${LOGFILE:-/dev/null}" 2>&1
        log "Exit code: $?"
        ;;
    Download)
        log "Event: $sonarr_eventtype | Series ID: $sonarr_series_id | File: $sonarr_episodefile_path"
        # Re-etiquetar por si los providers cambiaron
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
            "$TAGARR_CMD sonarr tag --id $sonarr_series_id" >> "${LOGFILE:-/dev/null}" 2>&1
        log "Tagging exit code: $?"
        if [ "$ENABLE_HARDLINKS" = true ]; then
            # Obtener tags actualizados desde la API de Sonarr
            updated_tags=$(curl -s -H "X-Api-Key: $SONARR_API_KEY" "$SONARR_URL/api/v3/series/$sonarr_series_id" \
                | jq -r '[.tags[] | tostring] | join("|")' 2>/dev/null)
            # Mapear IDs a nombres
            all_tags=$(curl -s -H "X-Api-Key: $SONARR_API_KEY" "$SONARR_URL/api/v3/tag")
            tag_names=$(echo "$updated_tags" | tr '|' '\n' | while read -r tid; do
                echo "$all_tags" | jq -r ".[] | select(.id == ($tid | tonumber)) | .label"
            done | paste -sd '|')
            create_hardlinks "$sonarr_episodefile_path" "$tag_names"
        fi
        ;;
    EpisodeFileDelete)
        log "Event: $sonarr_eventtype | Series ID: $sonarr_series_id | File: $sonarr_episodefile_path"
        if [ "$ENABLE_HARDLINKS" = true ]; then
            delete_episode_hardlinks "$sonarr_episodefile_path" "$sonarr_series_tags"
        fi
        ;;
    SeriesDelete)
        if [ "$sonarr_series_deletedfiles" = "True" ] && [ "$ENABLE_HARDLINKS" = true ]; then
            log "Event: $sonarr_eventtype | Series ID: $sonarr_series_id | DeletedFiles: True"
            parse_series_path
            streaming_base="$base_path/streaming"

            IFS='|' read -ra tags <<< "$sonarr_series_tags"
            for tag_name in "${tags[@]}"; do
                if [ -z "$tag_name" ] || [ "$tag_name" = "$NOT_AVAILABLE_TAG" ]; then
                    continue
                fi

                series_dir="$streaming_base/$tag_name/$series_type/$series_folder"
                if [ -d "$series_dir" ]; then
                    rm -rf "$series_dir"
                    log "Carpeta eliminada: $series_dir"
                else
                    log "Carpeta no encontrada: $series_dir"
                fi
            done
        fi
        ;;
    Test)
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" "echo 'Tagarr Sonarr: test OK'"
        ;;
esac
