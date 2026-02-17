#!/bin/bash
# Cron script para Radarr.
# Etiqueta y limpia etiquetas obsoletas de toda la biblioteca.
#
# Ejemplo de crontab (ejecutar cada día a las 3:00):
#   0 3 * * * /ruta/a/cron-radarr.sh
#
# Configuración:
#   TAGARR_VENV  - ruta al virtualenv de tagarr (dejar vacío si está instalado globalmente)
#   LOGFILE      - ruta al archivo de log (dejar vacío para desactivar)

TAGARR_VENV="${TAGARR_VENV:-}"
LOGFILE="${LOGFILE:-$HOME/.local/log/tagarr-cron-radarr.log}"

mkdir -p "$(dirname "$LOGFILE")"

if [ -n "$TAGARR_VENV" ]; then
    source "$TAGARR_VENV/bin/activate"
fi

log() {
    [ -n "$LOGFILE" ] && echo "[$(date)] $1" >> "$LOGFILE"
}

log "Inicio: tagarr radarr tag"
tagarr radarr tag >> "${LOGFILE:-/dev/null}" 2>&1
log "Exit code: $?"

log "Inicio: tagarr radarr clean"
tagarr radarr clean >> "${LOGFILE:-/dev/null}" 2>&1
log "Exit code: $?"
