#!/bin/bash
# Custom Script para Sonarr (Settings > Connect > Custom Script)
# Ejecuta tagarr por SSH en el host donde está instalado.
#
# Configuración:
#   TAGARR_HOST  - usuario@host donde está instalado tagarr
#   SSH_KEY      - ruta a la clave SSH privada
#   TAGARR_VENV  - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   LOGFILE      - ruta al archivo de log (dejar vacío para desactivar)

TAGARR_HOST="${TAGARR_HOST:-user@host}"
SSH_KEY="${SSH_KEY:-/root/.ssh/tagarr_key}"
TAGARR_VENV="${TAGARR_VENV:-}"
LOGFILE="${LOGFILE:-$HOME/.local/log/tagarr-sonarr.log}"

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    TAGARR_CMD="source $TAGARR_VENV/bin/activate && tagarr"
else
    TAGARR_CMD="tagarr"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

case "$sonarr_eventtype" in
    SeriesAdd)
        log "Event: $sonarr_eventtype | Series ID: $sonarr_series_id"
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" \
            "$TAGARR_CMD sonarr tag --id $sonarr_series_id" >> "${LOGFILE:-/dev/null}" 2>&1
        log "Exit code: $?"
        ;;
    Test)
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TAGARR_HOST" "echo 'Tagarr Sonarr: test OK'"
        ;;
esac
