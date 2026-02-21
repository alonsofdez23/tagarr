#!/bin/bash
# Cron script para sincronizar Sonarr con los providers actuales.
# Ejecutar en el LXC de Sonarr.
#
# Modos de uso:
#   cron-sonarr.sh              → solo etiquetado (tag + clean via SSH)
#   cron-sonarr.sh --hardlinks  → etiquetado + reconciliación de hardlinks
#
# Ejemplo de crontab:
#   0 4 * * * /usr/local/bin/cron-sonarr.sh
#   0 6 * * * /usr/local/bin/cron-sonarr.sh --hardlinks
#
# Configuración:
#   TAGARR_HOST       - usuario@host donde está instalado tagarr
#   SSH_KEY           - ruta a la clave SSH privada
#   TAGARR_VENV       - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   SONARR_URL        - URL de la API de Sonarr
#   SONARR_API_KEY    - clave API de Sonarr
#   NOT_AVAILABLE_TAG - etiqueta a excluir de los hardlinks (p. ej. no-streaming)
#   LOGFILE           - ruta al archivo de log (dejar vacío para desactivar)

TAGARR_HOST="${TAGARR_HOST:-user@host}"
SSH_KEY="${SSH_KEY:-/root/.ssh/tagarr_key}"
TAGARR_VENV="${TAGARR_VENV:-}"
SONARR_URL="${SONARR_URL:-http://localhost:8989}"
SONARR_API_KEY="${SONARR_API_KEY:-}"
NOT_AVAILABLE_TAG="${NOT_AVAILABLE_TAG:-no-streaming}"
LOGFILE="${LOGFILE:-/var/log/tagarr-sonarr-hardlinks.log}"

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
    "$TAGARR_CMD sonarr tag" >> "${LOGFILE:-/dev/null}" 2>&1
log "Tagging exit code: $?"

# 2. Limpiar tags obsoletos via SSH
log "Limpiando tags obsoletos..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
    "$TAGARR_CMD sonarr clean" >> "${LOGFILE:-/dev/null}" 2>&1
log "Clean exit code: $?"

if [ "$HARDLINKS" = false ]; then
    log "=== Sincronización completada ==="
    exit 0
fi

# 3. Obtener todos los tags de Sonarr (id -> nombre)
all_tags=$(curl -s -H "X-Api-Key: $SONARR_API_KEY" "$SONARR_URL/api/v3/tag")

# 4. Obtener todas las series
all_series=$(curl -s -H "X-Api-Key: $SONARR_API_KEY" "$SONARR_URL/api/v3/series")
series_count=$(echo "$all_series" | jq 'length')
log "Procesando $series_count series..."

# Archivo temporal para rutas de episodios (evita subshell anidado en pipe | while)
tmp_eps=$(mktemp)

echo "$all_series" | jq -c '.[]' | while read -r series; do
    series_path=$(echo "$series" | jq -r '.path')
    series_id=$(echo "$series" | jq -r '.id')
    tag_ids=$(echo "$series" | jq -r '.tags[]? // empty')

    # Extraer componentes de la ruta de la serie:
    #   series_path = /mnt/arrstack/tvseries/Yellowstone (2018) [tvdbid-341164]
    #   → series_root  = /mnt/arrstack/tvseries
    #   → base_path    = /mnt/arrstack
    #   → series_type  = tvseries (o anime, según carpeta raíz de Sonarr)
    #   → series_folder = Yellowstone (2018) [tvdbid-341164]
    series_root=$(dirname "$series_path")
    base_path=$(dirname "$series_root")
    series_type=$(basename "$series_root")
    series_folder=$(basename "$series_path")
    streaming_base="$base_path/streaming"

    # Obtener archivos de episodios de esta serie
    episode_files=$(curl -s -H "X-Api-Key: $SONARR_API_KEY" \
        "$SONARR_URL/api/v3/episodefile?seriesId=$series_id")
    ep_count=$(echo "$episode_files" | jq 'length')

    # Saltar series sin episodios descargados
    if [ "$ep_count" -eq 0 ]; then
        continue
    fi

    # Construir lista de provider tags actuales
    current_providers=()
    for tag_id in $tag_ids; do
        tag_name=$(echo "$all_tags" | jq -r ".[] | select(.id == $tag_id) | .label")
        if [ -n "$tag_name" ] && [ "$tag_name" != "$NOT_AVAILABLE_TAG" ]; then
            current_providers+=("$tag_name")
        fi
    done

    # Volcar rutas relativas a archivo temporal para iterar sin subshell adicional
    # relativePath es relativa a la carpeta de la serie, e.g.: Season 01/ep.mkv
    echo "$episode_files" | jq -r '.[].relativePath' > "$tmp_eps"

    while IFS= read -r episode_rel_path; do
        episode_file="$series_path/$episode_rel_path"

        # Saltar si el archivo no existe en disco
        [ -f "$episode_file" ] || continue

        # Añadir hardlinks faltantes
        for provider in "${current_providers[@]}"; do
            dest="$streaming_base/$provider/$series_type/$series_folder/$episode_rel_path"
            if [ ! -f "$dest" ]; then
                mkdir -p "$(dirname "$dest")"
                if ln "$episode_file" "$dest" 2>/dev/null; then
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
                hardlink="${provider_dir}${series_type}/$series_folder/$episode_rel_path"

                if [ -f "$hardlink" ]; then
                    # Comprobar si este provider sigue siendo un tag actual
                    found=false
                    for p in "${current_providers[@]}"; do
                        [ "$p" = "$provider" ] && found=true && break
                    done

                    if [ "$found" = false ]; then
                        rm "$hardlink"
                        log "Hardlink obsoleto eliminado: $hardlink"

                        # Eliminar carpeta de temporada si quedó vacía
                        season_dir=$(dirname "$hardlink")
                        if [ -z "$(ls -A "$season_dir" 2>/dev/null)" ]; then
                            rmdir "$season_dir"
                            log "Carpeta vacía eliminada: $season_dir"
                        fi
                    fi
                fi
            done
        fi
    done < "$tmp_eps"
done

rm -f "$tmp_eps"

log "=== Sincronización completada ==="
