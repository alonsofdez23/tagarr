import typer
import sys

from typing import Optional
from loguru import logger

import tagarr.commands.radarr as radarr
import tagarr.commands.sonarr as sonarr
import tagarr.commands.providers as providers

from tagarr import __version__


app = typer.Typer()
app.add_typer(radarr.app, name="radarr", help="Gestiona etiquetas de películas en Radarr.")
app.add_typer(sonarr.app, name="sonarr", help="Gestiona etiquetas de series en Sonarr.")
app.add_typer(
    providers.app, name="providers", help="Lista los proveedores de streaming disponibles para tu localización."
)


def version_callback(value: bool):
    if value:
        typer.echo(f"Tagarr: v{__version__}")
        raise typer.Exit()


def _setup_logging(debug):
    """
    Setup the log formatter for Tagarr
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"

    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        format="[{time:YYYY-MM-DD HH:mm:ss}] - <level>{message}</level>",
        level=log_level,
    )


@app.callback()
def main(
    debug: bool = False,
    version: Optional[bool] = typer.Option(None, "--version", callback=version_callback),
):
    """
    Tagarr etiqueta películas y series en Radarr/Sonarr con los proveedores de
    streaming en los que están disponibles (consultando JustWatch). También puede
    limpiar etiquetas obsoletas cuando el contenido deja de estar disponible.
    """

    # Setup the logger
    _setup_logging(debug)

    # Logging
    logger.debug(f"Starting Tagarr v{__version__}")


def cli():
    app(prog_name="tagarr")


if __name__ == "__main__":
    cli()
