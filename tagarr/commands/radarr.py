import rich
import typer

from typing import List, Optional
from loguru import logger

import tagarr.utils.output as output

from tagarr.core.radarr_actions import RadarrActions
from tagarr.utils.config import Config

app = typer.Typer()


@app.command(help="Etiqueta películas en Radarr con sus proveedores de streaming")
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
    Detect movies available on configured streaming providers and add tags
    in Radarr with the provider name (e.g. 'netflix', 'disney plus').
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

    # Setup Radarr Actions
    radarr = RadarrActions(config.radarr_url, config.radarr_api_key, locale)

    # Get movies to tag
    movies_to_tag = radarr.get_movies_to_tag(
        providers, config.fast_search, disable_progress,
        not_available_tag=config.not_available_tag
    )

    # Filter out excluded titles
    movies_to_tag = {
        id: values
        for id, values in movies_to_tag.items()
        if values["title"] not in config.radarr_excludes
    }

    if movies_to_tag:
        # Apply tags automatically
        radarr.tag_movies(movies_to_tag)

        # Print summary
        output.print_movies_tagged(movies_to_tag)

        rich.print(f"\nSuccessfully tagged {len(movies_to_tag)} movies in Radarr!")
    else:
        rich.print("No movies found on the configured streaming providers to tag.")


@app.command(help="Elimina etiquetas obsoletas de proveedores de streaming en Radarr")
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
    Find movies that have streaming provider tags but are no longer available
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

    # Setup Radarr Actions
    radarr = RadarrActions(config.radarr_url, config.radarr_api_key, locale)

    # Get movies to clean
    movies_to_clean = radarr.get_movies_to_clean(
        providers, config.fast_search, disable_progress,
        not_available_tag=config.not_available_tag
    )

    # Filter out excluded titles
    movies_to_clean = {
        id: values
        for id, values in movies_to_clean.items()
        if values["title"] not in config.radarr_excludes
    }

    if movies_to_clean:
        # Clean tags automatically
        radarr.clean_tags(movies_to_clean)

        # Print summary
        output.print_movies_cleaned(movies_to_clean)

        rich.print(f"\nSuccessfully cleaned tags from {len(movies_to_clean)} movies in Radarr!")
    else:
        rich.print("No movies with stale streaming provider tags found.")


@app.command(help="Elimina una etiqueta concreta de todas las películas en Radarr")
def purge_tag(
    tag: Optional[str] = typer.Option(
        None,
        "-t",
        "--tag",
        metavar="TAG",
        help="Etiqueta a eliminar. Por defecto usa not_available_tag del config.",
    ),
):
    """
    Elimina una etiqueta específica de todas las películas en Radarr.
    Si no se indica --tag, usa el valor de not_available_tag de la configuración.
    """
    logger.debug("Got purge-tag as subcommand")

    tag_label = tag or config.not_available_tag

    if not tag_label:
        rich.print("No se ha especificado etiqueta. Usa --tag o configura not_available_tag en el archivo de configuración.")
        raise typer.Exit(code=1)

    # Setup Radarr Actions (locale not needed but required by constructor)
    locale = config.locale or "en_US"
    radarr = RadarrActions(config.radarr_url, config.radarr_api_key, locale)

    # Get movies to purge
    movies_to_purge = radarr.get_movies_to_purge_tag(tag_label)

    if movies_to_purge:
        radarr.clean_tags(movies_to_purge)
        output.print_movies_cleaned(movies_to_purge)
        rich.print(f"\nEtiqueta '{tag_label}' eliminada de {len(movies_to_purge)} películas en Radarr.")
    else:
        rich.print(f"No se encontraron películas con la etiqueta '{tag_label}'.")


@app.callback()
def init():
    """
    Initializes the command. Reads the configuration.
    """
    logger.debug("Got radarr as subcommand")

    # Set globals
    global config
    global loglevel

    # Hacky way to get the current log level context
    loglevel = logger._core.min_level

    logger.debug("Reading configuration file")
    config = Config()


if __name__ == "__main__":
    app()
