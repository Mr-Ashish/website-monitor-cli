"""CLI entrypoint and command registration."""

from typing import Annotated

import typer

from cli_boilerplate import __version__
from cli_boilerplate.commands.demo import app as demo_app

app = typer.Typer(
    help="Website Monitor CLI boilerplate with polished terminal UX.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"website-monitor-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Root command group for all CLI commands."""
    _ = version


app.add_typer(demo_app, name="demo")


def main() -> None:
    """Console script entrypoint."""
    app()


if __name__ == "__main__":
    main()
