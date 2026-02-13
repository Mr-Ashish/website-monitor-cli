"""Shared Rich console and output helpers."""

from rich.console import Console

console = Console()


def print_info(message: str) -> None:
    console.print(f"[bold cyan]info:[/bold cyan] {message}")


def print_success(message: str) -> None:
    console.print(f"[bold green]success:[/bold green] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]warning:[/bold yellow] {message}")


def print_error(message: str) -> None:
    console.print(f"[bold red]error:[/bold red] {message}")
