"""CLI entrypoint and command registration."""

from typing import Annotated

import typer

from website_monitor_cli import __version__
# Import the monitor command group (replaces demo boilerplate)
from website_monitor_cli.commands.monitor import app as monitor_app

# Epilog with sample/copyable commands for root --help (Rich markup enabled;
# appears at bottom of `website-monitor --help` for easy user onboarding)
SAMPLE_COMMANDS = """
**Quick Start Examples** (copy and run these):

- Single check:  
  `website-monitor monitor check https://example.com --timeout 5`

- Continuous monitor (foreground):  
  `website-monitor monitor watch https://example.com --interval 30`

- Run as background job:  
  `website-monitor monitor watch https://example.com --background`

- Manage background jobs:  
  `website-monitor monitor status`  
  `website-monitor monitor logs <job-id>`  
  `website-monitor monitor stop <job-id>`

See `monitor --help` or README for all options/config (e.g., success status codes, bg PID/logs).
"""

app = typer.Typer(
    # Updated for website monitoring functionality + bg support
    help="Website Monitor CLI: check URLs, validate, and monitor HTTP status with configurable defaults.",
    no_args_is_help=True,
    add_completion=False,
    # Enable Rich markup in help/epilog for polished samples
    rich_markup_mode="rich",
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


# Register the monitor command group (provides check and watch subcommands)
# Epilog samples will appear in root --help
app.add_typer(monitor_app, name="monitor")

# Attach epilog (samples) after registration for root help
app.info.epilog = SAMPLE_COMMANDS


def main() -> None:
    """Console script entrypoint."""
    app()


if __name__ == "__main__":
    main()
