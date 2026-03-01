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
    load_job_config,
    log_check_result,
    send_webhook_notification,
    start_background,
    stop_job,
    update_job_config,
)
from website_monitor_cli.ui.console import (
    print_check_result,
    print_error,
    print_info,
    print_job_details,  # Full stats screen for details cmd
    print_jobs,
    print_logs,
    print_success,
    print_warning,  # For graceful empty details
)

app = typer.Typer(help="Monitor website availability via HTTP status checks. Short aliases: c=check, w=watch, s=status, st=stop, l=logs, d=details, u=update (e.g., 'monitor c <url>') for less typing.")


@app.command()
def check(
    url: str = typer.Argument(..., help="The website URL to check (must be valid http/https)."),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="HTTP timeout in seconds (overrides default)."
    ),
    verify_ssl: bool = typer.Option(
        True,
        "--verify-ssl/--no-verify",
        help="Verify SSL certificates for HTTPS requests. Use --no-verify to bypass SSL errors (e.g., self-signed certs).",
    ),
) -> None:
    """Perform a single check on the website URL.

    Validates the URL, sends request, checks status against success codes,
    and prints polished result table. Uses default config values.

    **Examples:**

    [green]Basic check:[/green]
      $ website-monitor monitor check https://example.com

    [green]Check with custom timeout:[/green]
      $ website-monitor monitor check https://example.com --timeout 5

    [green]Check bypassing SSL verification:[/green]
      $ website-monitor monitor check https://untrusted.com --no-verify

    [green]Short alias:[/green]
      $ website-monitor monitor c https://example.com -t 5
    """
    print_info(f"Checking website: {url}")

    # Build config with overrides
    config = Config()
    if timeout is not None:
        config.timeout = timeout
    config.verify_ssl = verify_ssl

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
    webhook_url: str | None = typer.Option(
        None,
        "--webhook-url",
        "-w",
        help="Webhook URL to notify on failure (POST request with failure details). "
        "Example: --webhook-url https://hooks.example.com/alert",
    ),
    webhook_payload: str | None = typer.Option(
        None,
        "--webhook-payload",
        help="Custom JSON payload template for webhook. Supports placeholders: "
        "{url}, {status_code}, {error}, {timestamp}, {response_time}. "
        "Example: --webhook-payload '{\"site\":\"{url}\",\"error\":\"{error}\"}'",
    ),
    verify_ssl: bool = typer.Option(
        True,
        "--verify-ssl/--no-verify",
        help="Verify SSL certificates for HTTPS requests. Use --no-verify to bypass SSL errors (e.g., self-signed certs).",
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
    Use --webhook-url to receive notifications on failures.
    Uses config defaults for interval, success status codes, etc.
    All options (incl. bg) appear in `watch --help`.

    **Examples:**

    [bold green]Basic watch (foreground):[/bold green]
      $ website-monitor monitor watch https://example.com --interval 30

    [bold green]Watch with webhook on failure:[/bold green]
      $ website-monitor monitor watch https://example.com --webhook-url https://hooks.example.com/alert

    [bold green]Watch with custom webhook payload:[/bold green]
      $ website-monitor monitor watch https://example.com -w https://hooks.example.com/alert --webhook-payload '{"site":"{url}","error":"{error}"}'

    [bold green]Background daemon with webhook:[/bold green]
      $ website-monitor monitor watch https://example.com --background --webhook-url https://hooks.example.com/alert

    [bold green]Short alias with webhook:[/bold green]
      $ website-monitor monitor w https://example.com -w https://hooks.example.com/alert -i 60
    """
    config = Config()
    if interval is not None:
        config.check_interval = interval
    if timeout is not None:
        config.timeout = timeout
    if background is not None:
        config.background = background
    if webhook_url is not None:
        config.webhook_url = webhook_url
    if webhook_payload is not None:
        config.webhook_payload = webhook_payload
    config.verify_ssl = verify_ssl

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
        if config.webhook_url:
            print_info(f"Webhook configured: {config.webhook_url}")
        print_info("Use 'monitor status' (shows uptime/avg/next ping), 'logs <job-id>', or 'stop <job-id>'.")
        return  # No loop in parent

    # Foreground mode (also logs for consistency/stats; bg daemon child hits this)
    # Initial check immediately (ensures first log entry , no empty history on details)
    # Then periodic; fixes common 'empty history' for fresh jobs.
    print_info(f"Starting monitor for {url} (interval: {config.check_interval}s)")
    if config.webhook_url:
        print_info(f"Webhook configured: {config.webhook_url}")
    print_info("Press Ctrl+C to stop")

    check_count = 0
    try:
        # First check/log always (before sleep)
        result = check_website(url, config)
        print_check_result(result)
        # Log structured JSONL for multi-entry history/stats (trim/rotate per config)
        log_check_result(result, log_file, config)
        # Trigger webhook on failure
        if not result.get("success", False) and config.webhook_url:
            webhook_result = send_webhook_notification(result, config)
            if not webhook_result.get("success"):
                print_warning(f"Webhook notification failed: {webhook_result.get('error')}")
        check_count += 1

        # Then loop for subsequent
        while max_checks is None or check_count < max_checks:
            # Reload config if running as a job (allows dynamic updates)
            if job_id:
                new_config_values = load_job_config(job_id, config)
                if new_config_values:
                    config.check_interval = new_config_values.get("interval", config.check_interval)
                    config.timeout = new_config_values.get("timeout", config.timeout)
                    config.webhook_url = new_config_values.get("webhook_url")
                    config.webhook_payload = new_config_values.get("webhook_payload")
                    config.verify_ssl = new_config_values.get("verify_ssl", config.verify_ssl)

            time.sleep(config.check_interval)
            result = check_website(url, config)
            print_check_result(result)
            log_check_result(result, log_file, config)
            # Trigger webhook on failure
            if not result.get("success", False) and config.webhook_url:
                webhook_result = send_webhook_notification(result, config)
                if not webhook_result.get("success"):
                    print_warning(f"Webhook notification failed: {webhook_result.get('error')}")
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

    Examples:
        website-monitor monitor status
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

    Examples:
        website-monitor monitor stop 12345
        website-monitor monitor stop example_com_a1b2c3d4
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

    Examples:
        website-monitor monitor logs 12345
        website-monitor monitor logs 12345 --lines 50
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

    Examples:
        website-monitor monitor details 12345
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




@app.command()
def update(
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to update."),
    interval: int | None = typer.Option(
        None,
        "--interval",
        "-i",
        min=5,
        help="New check interval in seconds.",
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="New HTTP timeout in seconds."
    ),
    webhook_url: str | None = typer.Option(
        None,
        "--webhook-url",
        "-w",
        help="New webhook URL (set to empty string "" to clear).",
    ),
    webhook_payload: str | None = typer.Option(
        None,
        "--webhook-payload",
        help="New webhook payload template (set to empty string "" to clear).",
    ),
    verify_ssl: bool | None = typer.Option(
        None,
        "--verify-ssl/--no-verify",
        help="Enable/disable SSL certificate verification.",
    ),
) -> None:
    """Update configuration of a running background monitor job.

    Updates the configuration file. The running job will pick up changes automatically.
    Only specified parameters are updated; others retain their current values.

    **Examples:**

    [bold green]Update check interval:[/bold green]
      $ website-monitor monitor update 12345 --interval 120

    [bold green]Disable SSL verification:[/bold green]
      $ website-monitor monitor update 12345 --no-verify

    [bold green]Update webhook URL:[/bold green]
      $ website-monitor monitor update 12345 --webhook-url https://new-hook.example.com

    [bold green]Clear webhook:[/bold green]
      $ website-monitor monitor update 12345 --webhook-url ""

    [bold green]Update multiple settings:[/bold green]
      $ website-monitor monitor update 12345 -i 60 -w https://hooks.example.com
    """
    config = Config()
    
    # Check that at least one update parameter is provided
    if all(param is None for param in [interval, timeout, webhook_url, webhook_payload, verify_ssl]):
        print_error("No updates specified. Provide at least one of: --interval, --timeout, --webhook-url, --webhook-payload, --verify-ssl/--no-verify")
        raise typer.Exit(1)
    
    print_info(f"Updating job {job_id}...")
    
    success = update_job_config(
        job_id,
        config,
        interval=interval,
        timeout=timeout,
        webhook_url=webhook_url,
        webhook_payload=webhook_payload,
        verify_ssl=verify_ssl,
    )
    
    if success:
        print_success(f"Job {job_id} configuration updated.")
        print_info("The running job will pick up the changes shortly.")
    else:
        print_error(f"Failed to update job {job_id}. Job may not exist or PID file is corrupt.")
        raise typer.Exit(1)


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
    verify_ssl: bool = typer.Option(
        False, "--verify-ssl/--no-verify", help="Verify SSL certificates for HTTPS requests.",
    ),
) -> None:
    """Short alias for 'check' (c <url>)."""
    check(url, timeout, verify_ssl)


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
    webhook_url: str | None = typer.Option(
        None, "--webhook-url", "-w", help="Webhook URL to notify on failure.",
    ),
    webhook_payload: str | None = typer.Option(
        None, "--webhook-payload", help="Custom JSON payload template for webhook.",
    ),
    verify_ssl: bool = typer.Option(
        False, "--verify-ssl/--no-verify", help="Verify SSL certificates for HTTPS requests.",
    ),
    # Internal job_id for bg sync (hidden, passed in alias too)
    job_id: str | None = typer.Option(
        None, "--job-id", hidden=True, help="Internal: pre-generated job ID for bg daemon."
    ),
) -> None:
    """Short alias for 'watch' (w <url> [options])."""
    watch(url, interval, timeout, max_checks, background, webhook_url, webhook_payload, verify_ssl, job_id)


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

@app.command("u")
def update_alias(
    job_id: str = typer.Argument(..., help="Job ID (or PID) from 'status' to update."),
    interval: int | None = typer.Option(
        None, "--interval", "-i", min=5, help="New check interval in seconds.",
    ),
    timeout: int | None = typer.Option(
        None, "--timeout", "-t", min=1, help="New HTTP timeout in seconds."
    ),
    webhook_url: str | None = typer.Option(
        None, "--webhook-url", "-w", help="New webhook URL.",
    ),
    webhook_payload: str | None = typer.Option(
        None, "--webhook-payload", help="New webhook payload template.",
    ),
    verify_ssl: bool | None = typer.Option(
        None, "--verify-ssl/--no-verify", help="Enable/disable SSL certificate verification.",
    ),
) -> None:
    """Short alias for 'update' (u <job-id|pid> [options])."""
    update(job_id, interval, timeout, webhook_url, webhook_payload, verify_ssl)

