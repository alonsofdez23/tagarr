import typer
from typing import Optional
from loguru import logger

from tagarr.modules.justwatch import justwatch
from tagarr.utils.config import Config
from tagarr.utils import output

app = typer.Typer()


@app.command(help="Muestra todos los proveedores de streaming disponibles para tu localización")
def list(
    locale: Optional[str] = typer.Option(
        None, "-l", "--locale", metavar="LOCALE", help="Tu localización, p. ej: es_ES."
    )
):
    # Check if locale is set on CLI otherwise get the value from the config
    if not locale:
        locale = config.locale

    justwatch_client = justwatch.JustWatch(locale)
    jw_providers = justwatch_client.get_providers()

    output.print_providers(jw_providers)


@app.callback()
def init():
    """
    Initializes the command. Reads the configuration.
    """
    logger.debug("Got providers as subcommand")

    # Set globals
    global config
    global loglevel

    # Hacky way to get the current log level context
    loglevel = logger._core.min_level

    logger.debug("Reading configuration file")
    config = Config()
