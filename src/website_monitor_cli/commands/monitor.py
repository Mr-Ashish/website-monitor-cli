"""Monitor commands for checking website status and availability.

Provides 'check' for one-time , 'watch' for continuous (foreground/bg) ,
and manager cmds (status/stop/logs) for bg jobs.
Uses PID files + detached subprocess for background capability.
All options (incl. --background) documented in --help.
"""

import time

import typer

from website_monitor_cli.config import Config
# Core funcs for check + bg daemon (start_background, list_jobs etc.)
from website_monitor_cli.core import (
    check_website,
    # For history/multi-entry logs + stats/details
    compute_job_stats,
    get_job_id,
    get_job_logs,
    get_log_file,
    list_jobs,
    log_check_result,
    start_background,
    stop_job,
)
from website_monitor_cli.ui.console import (
    print_check_result,
    print_error,
    print_info,
    print_jobs,
    print_job_details,  # Full stats screen for details cmd
    print_logs,
    print_success,
    print_warning,  # For graceful empty details
)

app = typer.Typer(help="Monitor website availability via HTTP status checks. Short aliases: c=check, w=watch, s=status, st=stop, l=logs, d=details (e.g., 'monitor c <url>') for less typing.")


@app.command()
def check(
    url: str = typer.Argument(..., help="The website URL to check (must be valid http/https)."),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="HTTP timeout in seconds (overrides default)."
    ),
) -> None:
    """Perform a single check on the website URL.

    Validates the URL, sends request, checks status against success codes,
    and prints polished result table. Uses default config values.
    """
    print_info(f"Checking website: {url}")

    # Build config with overrides
    config = Config()
    if timeout is not None:
        config.timeout = timeout

    result = check_website(url, config)
    print_check_result(result)


@app.command("watch")
def watch(
    url: str = typer.Argument(..., help="The website URL to monitor continuously."),
    interval: int = typer.Option(
        None,
        "--interval",
        "-i",
        min=5,
        help="Check interval in seconds (default from config).",
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="HTTP timeout in seconds."
    ),
    max_checks: int | None = typer.Option(
        None,
        "--max-checks",
        "-m",
        min=1,
        help="Maximum checks before stopping (unlimited if not set).",
    ),
    background: bool = typer.Option(
        None,
        "--background",
        "-b",
        help="Run as background daemon job (uses PID/log files; enables stop/status/logs). "
        "Overrides config.background. See root --help for samples.",
    ),
    # Internal/hidden for bg daemon sync (ensures parent/child use same job_id for logs/PID;
    # prevents mismatch where entries not populated in stats/details).
    job_id: str | None = typer.Option(
        None, "--job-id", hidden=True, help="Internal: pre-generated job ID for bg daemon."
    ),
) -> None:
    """Continuously monitor the website with periodic checks.

    Foreground by default (Ctrl+C to stop). Use --background for daemon job
    (detached subprocess, nohup-style). Manage via status/stop/logs.
    Logs timestamped checks (multiple entries over time) for stats (uptime, avg resp,
    pings in status screen; uses config max_log_entries/rotate).
    Uses config defaults for interval, success status codes, etc.
    All options (incl. bg) appear in `watch --help`.
    """
    config = Config()
    if interval is not None:
        config.check_interval = interval
    if timeout is not None:
        config.timeout = timeout
    if background is not None:
        config.background = background

    # Setup for history logging (multi-entry; bg or fg)
    # Use provided job_id (for bg daemon sync) or generate (normal fg)
    # Fixes bug where child subprocess regenerated UUID -> missing log entries in stats.
    if job_id is None:
        job_id = get_job_id(url)
    log_file = get_log_file(config, job_id)
    if config.background:
        # Bg mode: daemonize and return job info (daemon will log)
        print_info(f"Starting background monitor for {url}")
        job = start_background(url, config)
        if "error" in job:
            print_error(f"Failed to start bg job: {job['error']}")
            raise typer.Exit(1)
        # Update job_data with job_id/log for stats
        job["job_id"] = job_id  # Ensure
        # Note: daemon re-runs watch , which will log here? Wait , bg cmd skips
        # For bg , log initial ; daemon loop adds entries
        print_success(f"Background job started: job_id={job_id}, pid={job['pid']}")
        print_info(f"Log: {log_file} (appends timestamped checks for history/stats)")
        print_info("Use 'monitor status' (shows uptime/avg/next ping), 'logs <job-id>', or 'stop <job-id>'.")
        return  # No loop in parent

    # Foreground mode (also logs for consistency/stats; bg daemon child hits this)
    # Initial check immediately (ensures first log entry , no empty history on details)
    # Then periodic; fixes common 'empty history' for fresh jobs.
    print_info(f"Starting monitor for {url} (interval: {config.check_interval}s)")
    print_info("Press Ctrl+C to stop")

    check_count = 0
    try:
        # First check/log always (before sleep)
        result = check_website(url, config)
        print_check_result(result)
        # Log structured JSONL for multi-entry history/stats (trim/rotate per config)
        log_check_result(result, log_file, config)
        check_count += 1

        # Then loop for subsequent
        while max_checks is None or check_count < max_checks:
            time.sleep(config.check_interval)
            result = check_website(url, config)
            print_check_result(result)
            log_check_result(result, log_file, config)
            check_count += 1
    except KeyboardInterrupt:
        print_info("Monitoring stopped by user")
    else:
        print_success(f"Completed {check_count} checks")


@app.command()
def status() -> None:
    """List all background monitor jobs (PIDs, URLs, status, logs) + quick uptime %.

    De-cluttered overview; use 'details <job-id|pid>' for cumulated dashboard
    (start_time, next_run, uptime % from start, total_pings, failures etc.).
    Part of bg capability.
    """
    config = Config()
    jobs = list_jobs(config)
    # Use shared UI helper for polished (de-cluttered) table
    print_jobs(jobs)
    if jobs:
        print_info("Use 'monitor details <job-id|pid>' for cumulated dashboard (start_time, uptime, failures, pings etc.), 'logs <job-id|pid>' or 'stop <job-id|pid>'.")


@app.command()
def stop(
    # Accepts job_id or PID (resolved in core.stop_job via resolve_job_id)
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to stop."),
) -> None:
    """Stop a background monitor job by job_id *or* PID (sends SIGTERM/SIGKILL).

    PID support added for convenience (resolves to job_id/PID file internally).
    """
    config = Config()
    if stop_job(job_id, config):
        print_success(f"Job {job_id} stopped successfully.")
    else:
        print_error(f"Failed to stop job {job_id} (not found or error).")
        raise typer.Exit(1)


@app.command()
def logs(
    # Accepts job_id or PID (resolved in core.get_job_logs via resolve_job_id)
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to view logs."),
    lines: int = typer.Option(20, "--lines", "-n", help="Number of log lines to tail."),
) -> None:
    """View recent logs from a background job's log file.

    Accepts job_id *or* PID for convenience.
    """
    config = Config()
    log_output = get_job_logs(job_id, config, lines)
    # Use shared UI helper
    print_logs(log_output, job_id)


@app.command()
def details(
    # Accepts job_id or PID (resolved in core.compute_job_stats/get_job_logs)
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' for cumulated details dashboard."),
) -> None:
    """Show cumulated details *dashboard* for job (start_time, next_run, uptime %,
    total_pings, failures, successes, avg resp etc. from start).

    Uses enhanced compute_job_stats (PID/job_id support); Rich dashboard view
    (tables + panels). De-clutters status; deep dive for history.
    Graceful for new/empty jobs (partial dashboard + warn).
    """
    config = Config()
    # Compute cumulated stats/metadata (resolves PID if provided)
    stats = compute_job_stats(job_id, config)

    # Render full dashboard UI (handles empty gracefully)
    print_job_details(stats, job_id)

    # Always preview raw logs (even partial; supports PID)
    log_preview = get_job_logs(job_id, config, lines=5)
    print_logs(log_preview, job_id)
    print_info("Use 'status' for overview or 'logs <job-id|pid> --lines N' for raw checks. Wait interval for fresh data.")


# Short aliases for subcommands (reduces typing: e.g., 'monitor c <url>' for check,
# 'w' for watch, 's' for status, 'st' for stop, 'l' for logs, 'd' for details.
# Wrappers delegate to originals for logic; documented in --help; all options
# (e.g., -t, -i, -b) remain available. Update epilog/README for usability.
@app.command("c")
def check_alias(
    url: str = typer.Argument(..., help="The website URL to check (must be valid http/https)."),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="HTTP timeout in seconds (overrides default)."
    ),
) -> None:
    """Short alias for 'check' (c <url>)."""
    check(url, timeout)


@app.command("w")
def watch_alias(
    url: str = typer.Argument(..., help="The website URL to monitor continuously."),
    interval: int = typer.Option(
        None, "--interval", "-i", min=5, help="Check interval in seconds (default from config).",
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="HTTP timeout in seconds."
    ),
    max_checks: int | None = typer.Option(
        None, "--max-checks", "-m", min=1, help="Maximum checks before stopping (unlimited if not set).",
    ),
    background: bool = typer.Option(
        None, "--background", "-b", help="Run as background daemon job (...).",
    ),
    # Internal job_id for bg sync (hidden, passed in alias too)
    job_id: str | None = typer.Option(
        None, "--job-id", hidden=True, help="Internal: pre-generated job ID for bg daemon."
    ),
) -> None:
    """Short alias for 'watch' (w <url> [options])."""
    watch(url, interval, timeout, max_checks, background, job_id)


@app.command("s")
def status_alias() -> None:
    """Short alias for 'status' (s)."""
    status()


@app.command("st")
def stop_alias(
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to stop."),
) -> None:
    """Short alias for 'stop' (st <job-id|pid>)."""
    stop(job_id)


@app.command("l")
def logs_alias(
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to view logs."),
    lines: int = typer.Option(20, "--lines", "-n", help="Number of log lines to tail."),
) -> None:
    """Short alias for 'logs' (l <job-id|pid> [--lines N])."""
    logs(job_id, lines)


@app.command("d")
def details_alias(
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' for cumulated details dashboard."),
) -> None:
    """Short alias for 'details' (d <job-id|pid>)."""
    details(job_id)
