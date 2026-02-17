import rich
import typer

from typing import List, Optional
from loguru import logger

import tagarr.utils.output as output

from tagarr.core.sonarr_actions import SonarrActions
from tagarr.utils.config import Config

app = typer.Typer()


@app.command(help="Etiqueta series en Sonarr con sus proveedores de streaming")
def tag(
    providers: Optional[List[str]] = typer.Option(
        None,
        "-p",
        "--provider",
        metavar="PROVIDER",
        help="Sobrescribe los proveedores de streaming configurados.",
    ),
    locale: Optional[str] = typer.Option(
        None, "-l", "--locale", metavar="LOCALE", help="Tu localización, p. ej: es_ES."
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Muestra una barra de progreso."
    ),
):
    """
    Detect series available on configured streaming providers and add tags
    in Sonarr with the provider name (e.g. 'netflix', 'disney plus').
    Tags are applied at the series level.
    """
    logger.debug("Got tag as subcommand")
    logger.debug(f"Got CLI values for --progress option: {progress}")

    # Disable the progress bar when debug logging is active
    if loglevel == 10:
        disable_progress = True
    elif progress and loglevel != 10:
        disable_progress = False
    else:
        disable_progress = True

    # Determine if CLI options should overwrite configuration settings
    if not providers:
        providers = config.providers
    if not locale:
        locale = config.locale

    # Setup Sonarr Actions
    sonarr = SonarrActions(config.sonarr_url, config.sonarr_api_key, locale)

    # Get series to tag
    series_to_tag = sonarr.get_series_to_tag(
        providers, config.fast_search, disable_progress, tmdb_api_key=config.tmdb_api_key
    )

    # Filter out excluded titles
    series_to_tag = {
        id: values
        for id, values in series_to_tag.items()
        if values["title"] not in config.sonarr_excludes
    }

    if series_to_tag:
        # Apply tags automatically
        sonarr.tag_series(series_to_tag)

        # Print summary
        output.print_series_tagged(series_to_tag)

        rich.print(f"\nSuccessfully tagged {len(series_to_tag)} series in Sonarr!")
    else:
        rich.print("No series found on the configured streaming providers to tag.")


@app.command(help="Elimina etiquetas obsoletas de proveedores de streaming en Sonarr")
def clean(
    providers: Optional[List[str]] = typer.Option(
        None,
        "-p",
        "--provider",
        metavar="PROVIDER",
        help="Sobrescribe los proveedores de streaming configurados.",
    ),
    locale: Optional[str] = typer.Option(
        None, "-l", "--locale", metavar="LOCALE", help="Tu localización, p. ej: es_ES."
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Muestra una barra de progreso."
    ),
):
    """
    Find series that have streaming provider tags but are no longer available
    on those providers, and remove the stale tags.
    """
    logger.debug("Got clean as subcommand")
    logger.debug(f"Got CLI values for --progress option: {progress}")

    # Disable the progress bar when debug logging is active
    if loglevel == 10:
        disable_progress = True
    elif progress and loglevel != 10:
        disable_progress = False
    else:
        disable_progress = True

    # Determine if CLI options should overwrite configuration settings
    if not providers:
        providers = config.providers
    if not locale:
        locale = config.locale

    # Setup Sonarr Actions
    sonarr = SonarrActions(config.sonarr_url, config.sonarr_api_key, locale)

    # Get series to clean
    series_to_clean = sonarr.get_series_to_clean(
        providers, config.fast_search, disable_progress, tmdb_api_key=config.tmdb_api_key
    )

    # Filter out excluded titles
    series_to_clean = {
        id: values
        for id, values in series_to_clean.items()
        if values["title"] not in config.sonarr_excludes
    }

    if series_to_clean:
        # Clean tags automatically
        sonarr.clean_tags(series_to_clean)

        # Print summary
        output.print_series_cleaned(series_to_clean)

        rich.print(f"\nSuccessfully cleaned tags from {len(series_to_clean)} series in Sonarr!")
    else:
        rich.print("No series with stale streaming provider tags found.")


@app.callback()
def init():
    """
    Initializes the command. Reads the configuration.
    """
    logger.debug("Got sonarr as subcommand")

    # Set globals
    global config
    global loglevel

    # Hacky way to get the current log level context
    loglevel = logger._core.min_level

    logger.debug("Reading configuration file")
    config = Config()


if __name__ == "__main__":
    app()
