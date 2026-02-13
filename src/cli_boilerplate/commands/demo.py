"""Demo command group showing Rich UI primitives."""

from time import sleep

import typer
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from cli_boilerplate.ui.console import print_info, print_success

app = typer.Typer(help="Demonstrate polished terminal UI patterns.")


@app.command("run")
def run_demo(
    total: int = typer.Option(20, min=1, help="Number of units to process."),
    delay: float = typer.Option(0.03, min=0.0, help="Sleep delay per unit in seconds."),
) -> None:
    """Run a simple workflow with panel, table, and progress bar."""
    print_info("Starting demo workflow")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ) as progress:
        task_id = progress.add_task("Processing", total=total)
        for _ in range(total):
            sleep(delay)
            progress.advance(task_id)

    results_table = Table(title="Demo Results")
    results_table.add_column("Metric", style="bold")
    results_table.add_column("Value")
    results_table.add_row("Items processed", str(total))
    results_table.add_row("Delay per item", f"{delay:.3f}s")
    results_table.add_row("Status", "Complete")
    print_info("Rendering report")
    from cli_boilerplate.ui.console import console

    console.print(results_table)
    console.print(Panel.fit("Demo complete. Use this pattern for real commands.", title="Done"))
    print_success("Demo command finished")
