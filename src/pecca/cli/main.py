import typer

from pecca import __version__

app = typer.Typer(help="Pecca CLI", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Pecca CLI."""


@app.command()
def version() -> None:
    """Print the Pecca version."""
    typer.echo(__version__)
