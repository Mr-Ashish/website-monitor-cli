"""Shared Rich console and output helpers."""

from datetime import datetime, timedelta  # For human-readable timestamps/durations in dashboard
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# For stats in jobs table (uptime etc from history logs)
from website_monitor_cli.config import Config
from website_monitor_cli.core import compute_job_stats

console = Console()


def format_timestamp(iso_str: str | None) -> str:
    """Format ISO timestamp to user-friendly string (e.g., '2024-02-17 21:52:06').

    Fallback for None/invalid; keeps dashboard readable.
    """
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", ""))  # Handle ISO variants
        return dt.strftime("%Y-%m-%d %H:%M:%S")  # Simple, readable local
    except Exception:
        return str(iso_str)  # Fallback


def format_duration(seconds: float | int | None) -> str:
    """Format seconds to human-readable duration (e.g., '2 days 3h 45m 12s').

    Used for elapsed time, time to next run, uptime deltas etc. in dashboard.
    Handles <1min, days+; stdlib timedelta for accuracy.
    """
    if seconds is None or seconds < 0:
        return "N/A"
    try:
        delta = timedelta(seconds=float(seconds))
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:  # Always show secs if <1min
            parts.append(f"{secs}s")
        return " ".join(parts)
    except Exception:
        return f"{seconds}s"  # Fallback


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
    # PID support: users can now use PID for details/logs/stop
    print_success(f"Found {len(jobs)} job(s). Use 'details <job-id|pid>' for full stats (avg resp, pings etc.).")



def print_logs(log_output: str, job_id: str) -> None:
    """Print job logs (tail) with header for bg job debugging.

    job_id param accepts job_id *or* PID (resolved upstream in core).
    """
    print_info(f"Logs for job {job_id} (recent lines):")
    # Echo raw logs (check results, errors)
    console.print(log_output or "No log content.")
    print_success("End of logs. Use 'status' to check job state.")


def print_job_details(stats: dict[str, Any], job_id: str) -> None:
    """Cumulated details *dashboard* for a single job (Rich tables + panels).

    Accepts job_id *or* PID (resolved upstream via core.resolve_job_id).
    Shows all cumulated details from start: start_time, next_run_time, uptime %,
    total_pings, failures, successes, avg resp, etc. (enhanced from prior list).

    Per-job dashboard view (de-clutters status; pulls PID metadata + log history).
    Gracefully handles empty/new job (partial dashboard from metadata + warn).
    """
    # Always show core job info (even for empty history; fixed data flow from logs/PID)
    # URL prioritized from logs entries (persists post-stop); start_time from PID/log.
    # Error details always included for user visibility (no hidden issues).
    job_url = stats.get("url", "N/A")
    start_time = stats.get("start_time", "N/A")
    console.print(Panel.fit(
        f"Job: {job_id}\nURL: {job_url}\nStarted: {start_time}",
        title="📊 Job Dashboard Overview",
        border_style="bold blue",
    ))

    if "error" in stats:
        # Partial dashboard for fresh/empty; *print full error* + guide for visibility
        # (e.g., "Empty history..." so user knows exact issue; no silent N/A)
        print_warning(f"{stats['error']} for job {job_id} (partial dashboard shown)")
        print_info("Tip: Job too new? Wait one interval or run a check. Logs build over time for full stats.")
        # Error details panel for clarity
        console.print(Panel.fit(
            f"Issue: {stats['error']}\nJob ID/PID: {job_id}\nURL (if avail): {job_url}",
            title="Error Details",
            border_style="yellow",
        ))
        # Still show guide panel
        console.print(Panel.fit(
            "Run 'monitor logs <job-id|pid>' for raw checks or wait for pings.",
            title="Next Steps",
        ))
        return

    # Main dashboard table: cumulated details with user-friendly times/durations
    # (e.g., '2024-02-17 21:52:06', '2 days 3h 45m 12s'; uses helpers for readability)
    table = Table(title=f"Cumulated Stats for Job {job_id}", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")
    # Timestamps formatted readable
    table.add_row("Start Time", format_timestamp(stats.get("start_time")))
    table.add_row("Next Run Time", format_timestamp(stats.get("next_run_time")))
    # Durations in days/h/m/s
    table.add_row("Time Since Start", format_duration(stats.get("time_since_start_seconds")))
    table.add_row("Next Run In", format_duration(stats.get("next_run_in_seconds")))
    table.add_row("Uptime % (from start)", f"{stats.get('uptime_pct', 0):.2f}%")
    table.add_row("Total Pings", str(stats.get("total_pings", 0)))
    table.add_row("Successes", str(stats.get("success_count", 0)))
    table.add_row("Failures", str(stats.get("failures", 0)))  # Cumulated
    table.add_row("Avg Response Time", f"{stats.get('avg_response_time', 0):.3f}s")
    table.add_row("Last Ping", format_timestamp(stats.get("last_ping")))
    console.print(table)

    # History/period panel + summary (format timestamps readable)
    period_start = format_timestamp(stats.get("period_start"))
    period_end = format_timestamp(stats.get("period_end"))
    console.print(Panel.fit(
        f"{period_start} to {period_end}",
        title="Monitoring Period",
        border_style="green",
    ))

    # Final summary panel
    console.print(Panel.fit(
        "View raw: 'monitor logs <job-id|pid>' | Overview: 'monitor status'",
        title="Dashboard Summary",
    ))
    print_success("Cumulated job dashboard complete.")

