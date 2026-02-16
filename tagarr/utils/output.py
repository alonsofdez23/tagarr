from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box


def print_movies_tagged(movies):
    console = Console()

    table = Table(show_footer=False, row_styles=["none", "dim"], box=box.MINIMAL, pad_edge=False)
    with Live(table, console=console, screen=False):
        table.add_column("Title")
        table.add_column("Providers Tagged")

        for _, movie in movies.items():
            title = movie["title"]
            providers = ", ".join(movie["providers"])

            table.add_row(title, providers)


def print_series_tagged(series):
    console = Console()

    table = Table(show_footer=False, row_styles=["none", "dim"], box=box.MINIMAL, pad_edge=False)
    with Live(table, console=console, screen=False):
        table.add_column("Title")
        table.add_column("Providers Tagged")

        for _, serie in series.items():
            title = serie["title"]
            providers = ", ".join(serie["providers"])

            table.add_row(title, providers)


def print_movies_cleaned(movies):
    console = Console()

    table = Table(show_footer=False, row_styles=["none", "dim"], box=box.MINIMAL, pad_edge=False)
    with Live(table, console=console, screen=False):
        table.add_column("Title")
        table.add_column("Tags Removed")

        for _, movie in movies.items():
            title = movie["title"]
            tags_removed = ", ".join(movie["tags_removed"])

            table.add_row(title, tags_removed)


def print_series_cleaned(series):
    console = Console()

    table = Table(show_footer=False, row_styles=["none", "dim"], box=box.MINIMAL, pad_edge=False)
    with Live(table, console=console, screen=False):
        table.add_column("Title")
        table.add_column("Tags Removed")

        for _, serie in series.items():
            title = serie["title"]
            tags_removed = ", ".join(serie["tags_removed"])

            table.add_row(title, tags_removed)


def print_providers(providers):
    console = Console()

    table = Table(show_footer=False, row_styles=["none", "dim"], box=box.MINIMAL, pad_edge=False)
    with Live(table, console=console, screen=False):
        table.add_column("JustWatch ID")
        table.add_column("Provider")

        for provider in providers:
            id = str(provider["id"])
            clear_name = provider["clear_name"]

            table.add_row(id, clear_name)
