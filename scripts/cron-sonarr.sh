#!/bin/bash
# Cron script para Sonarr.
# Etiqueta y limpia etiquetas obsoletas de toda la biblioteca.
#
# Ejemplo de crontab (ejecutar cada día a las 4:00):
#   0 4 * * * /ruta/a/cron-sonarr.sh
#
# Configuración:
#   TAGARR_VENV  - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   LOGFILE      - ruta al archivo de log (dejar vacío para desactivar)

TAGARR_VENV="${TAGARR_VENV:-}"
LOGFILE="${LOGFILE:-$HOME/.local/log/tagarr-cron-sonarr.log}"

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    source "$TAGARR_VENV/bin/activate"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

log "Inicio: tagarr sonarr tag"
tagarr sonarr tag >> "${LOGFILE:-/dev/null}" 2>&1
log "Exit code: $?"

log "Inicio: tagarr sonarr clean"
tagarr sonarr clean >> "${LOGFILE:-/dev/null}" 2>&1
log "Exit code: $?"
