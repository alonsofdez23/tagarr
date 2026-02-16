import typer
import sys

from typing import Optional
from loguru import logger

import tagarr.commands.radarr as radarr
import tagarr.commands.sonarr as sonarr
import tagarr.commands.providers as providers

from tagarr import __version__


app = typer.Typer()
app.add_typer(radarr.app, name="radarr", help="Manages movies in Radarr.")
app.add_typer(sonarr.app, name="sonarr", help="Manages TV shows in Sonarr.")
app.add_typer(
    providers.app, name="providers", help="List all the possible providers for your locale."
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
    Tagarr is a CLI that interacts with Radarr and Sonarr instances. It detects
    movies and series available on configured streaming providers and adds tags
    in Radarr/Sonarr identifying which streaming services each title is available on.
    It can also clean up stale tags when content is no longer on a provider.
    """

    # Setup the logger
    _setup_logging(debug)

    # Logging
    logger.debug(f"Starting Tagarr v{__version__}")


def cli():
    app(prog_name="tagarr")


if __name__ == "__main__":
    cli()
