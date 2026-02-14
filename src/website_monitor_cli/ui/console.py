"""Shared Rich console and output helpers."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# For stats in jobs table (uptime etc from history logs)
from website_monitor_cli.config import Config
from website_monitor_cli.core import compute_job_stats

console = Console()


def print_info(message: str) -> None:
    """Print informational message in cyan."""
    console.print(f"[bold cyan]info:[/bold cyan] {message}")


def print_success(message: str) -> None:
    """Print success message in green."""
    console.print(f"[bold green]success:[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print warning message in yellow."""
    console.print(f"[bold yellow]warning:[/bold yellow] {message}")


def print_error(message: str) -> None:
    """Print error message in red."""
    console.print(f"[bold red]error:[/bold red] {message}")


def print_check_result(result: dict[str, Any]) -> None:
    """Print website check result using a Rich table for polished UX.

    Includes status code, success indicator, response time, and any error.
    """
    url = result.get("url", "unknown")
    table = Table(title=f"Check Result for {url}")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    status_code = result.get("status_code", "N/A")
    table.add_row("Status Code", str(status_code))

    success = result.get("success", False)
    success_str = "✅ Success" if success else "❌ Failed"
    table.add_row("Status", success_str)

    resp_time = result.get("response_time", 0.0)
    table.add_row("Response Time", f"{resp_time}s")

    error = result.get("error")
    if error:
        table.add_row("Error", str(error), style="red")

    console.print(table)

    if success:
        print_success("Website is up and responding successfully")
    else:
        print_error("Website check failed")


def print_jobs(jobs: list[dict[str, Any]]) -> None:
    """Print background jobs list using Rich table (for status cmd; de-cluttered).

    Shows PID, running state, logs path + quick uptime% from history.
    Full details (avg resp, last/next ping, checks) moved to per-job 'details <job-id>' screen.
    """
    if not jobs:
        print_info("No background jobs found.")
        return

    # Config + quick uptime from history (keep simple)
    config = Config()

    table = Table(title="Background Monitor Jobs")
    table.add_column("Job ID", style="bold")
    table.add_column("URL")
    table.add_column("PID")
    table.add_column("Running")
    table.add_column("Started")
    table.add_column("Uptime %", style="green")  # Quick stat retained
    table.add_column("Log")

    for job in jobs:
        # Only compute uptime for de-cluttered view
        stats = compute_job_stats(job.get("job_id", ""), config)
        running_str = "✅ Yes" if job.get("running") else "❌ No"
        uptime_str = f"{stats.get('uptime_pct', 0):.1f}%" if "uptime_pct" in stats else "N/A"
        table.add_row(
            job.get("job_id", "N/A"),
            job.get("url", "N/A"),
            str(job.get("pid", "N/A")),
            running_str,
            job.get("started_at", "N/A"),
            uptime_str,
            job.get("log_file", "N/A"),
        )
    console.print(table)
    print_success(f"Found {len(jobs)} job(s). Use 'details <job-id>' for full stats (avg resp, pings etc.).")



def print_logs(log_output: str, job_id: str) -> None:
    """Print job logs (tail) with header for bg job debugging."""
    print_info(f"Logs for job {job_id} (recent lines):")
    # Echo raw logs (check results, errors)
    console.print(log_output or "No log content.")
    print_success("End of logs. Use 'status' to check job state.")


def print_job_details(stats: dict[str, Any], job_id: str) -> None:
    """Rich details screen (table + panel) for a specific job ID.

    Shows full stats de-cluttered from status: uptime, avg resp time,
    last/next ping, checks, period. Per-job deep view.
    Gracefully handles empty/new job (no error; info/warn instead).
    """
    if "error" in stats:
        # Not error for fresh jobs (e.g., before first ping); warn + guide
        print_warning(f"No history yet for job {job_id}: {stats['error']}")
        print_info("Tip: Job too new? Wait one interval or run a check. Logs build over time.")
        return

    # Table for stats
    table = Table(title=f"Detailed Stats for Job {job_id}")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Uptime %", f"{stats.get('uptime_pct', 0):.2f}%")
    table.add_row("Avg Response Time", f"{stats.get('avg_response_time', 0):.3f}s")
    table.add_row("Last Ping", stats.get("last_ping", "N/A"))
    table.add_row("Next Ping (est.)", stats.get("next_ping", "N/A"))
    table.add_row("Total Checks", str(stats.get("total_checks", 0)))
    table.add_row("Success Count", str(stats.get("success_count", 0)))
    console.print(table)

    # Summary panel
    period = f"{stats.get('period_start', 'N/A')} to {stats.get('period_end', 'N/A')}"
    console.print(Panel.fit(period, title="Monitoring Period"))

    print_success("Details screen complete. Use 'status' for overview or 'logs' for raw data.")

