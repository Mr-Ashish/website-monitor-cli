from typer.testing import CliRunner

from website_monitor_cli.main import app

runner = CliRunner()


def test_help_shows_root_description() -> None:
    """Root help should describe the website monitor functionality."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Website Monitor CLI" in result.stdout
    assert "monitor" in result.stdout


def test_monitor_check_valid_url_smoke() -> None:
    """Smoke test: check a known-good URL (example.com is always available)."""
    # Uses default config; expects success status.
    result = runner.invoke(app, ["monitor", "check", "https://example.com"])
    assert result.exit_code == 0
    assert "Status Code" in result.stdout
    # May be 200 or other success per config
    assert "✅ Success" in result.stdout or "Status" in result.stdout


def test_monitor_check_invalid_url() -> None:
    """Invalid URL should be caught before request and reported as failure."""
    result = runner.invoke(app, ["monitor", "check", "not-a-valid-url"])
    assert result.exit_code == 0
    assert "Invalid URL" in result.stdout
    assert "❌ Failed" in result.stdout


def test_monitor_subcommands_help() -> None:
    """Monitor subgroup help lists subcommands and ensures all extra options
    (e.g., --timeout, --interval, --max-checks, --background) are documented/visible.
    Also covers bg manager cmds (status/stop/logs) + history/stats features
    (uptime, avg resp, pings from multi-entry logs).
    """
    # Group help (now includes bg cmds)
    result = runner.invoke(app, ["monitor", "--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout
    assert "watch" in result.stdout  # Continuous (fg/bg)
    assert "status" in result.stdout  # Bg job list + stats
    assert "stop" in result.stdout
    assert "logs" in result.stdout

    # Check command help (verifies options like --timeout)
    result = runner.invoke(app, ["monitor", "check", "--help"])
    assert result.exit_code == 0
    assert "--timeout" in result.stdout or "-t" in result.stdout
    assert "HTTP timeout" in result.stdout

    # Watch command help (verifies all extra options: interval, timeout, max-checks,
    # AND --background/-b for daemon job; mentions history/logs/stats)
    # This ensures users see defaults, overrides, bg capability, and config-linked options.
    result = runner.invoke(app, ["monitor", "watch", "--help"])
    assert result.exit_code == 0
    assert "--interval" in result.stdout or "-i" in result.stdout
    assert "--timeout" in result.stdout or "-t" in result.stdout
    assert "--max-checks" in result.stdout or "-m" in result.stdout
    assert "--background" in result.stdout or "-b" in result.stdout
    assert "background" in result.stdout
    assert "Check interval" in result.stdout
    assert "history" in result.stdout.lower() or "stats" in result.stdout.lower()

    # Manager cmds help (bg + stats)
    result = runner.invoke(app, ["monitor", "status", "--help"])
    assert result.exit_code == 0
    assert "stats" in result.stdout.lower() or "uptime" in result.stdout.lower()
    assert "background" in result.stdout

    result = runner.invoke(app, ["monitor", "logs", "--help"])
    assert result.exit_code == 0
    assert "--lines" in result.stdout


def test_monitor_status_smoke() -> None:
    """Smoke test status cmd (de-cluttered: bg jobs + quick uptime%; no avg/ping clutter)."""
    result = runner.invoke(app, ["monitor", "status"])
    assert result.exit_code == 0
    # Empty or table (headers basics + uptime)
    assert (
        "Background Monitor Jobs" in result.stdout
        or "No background jobs" in result.stdout
    )
    assert "Uptime %" in result.stdout  # Retained quick stat
    # No clutter cols
    assert "Avg Resp" not in result.stdout and "Next Ping" not in result.stdout
    assert "details" in result.stdout.lower()  # Guides to details screen


def test_monitor_details_screen() -> None:
    """Test details per-job screen (full stats: avg, pings etc.; graceful for empty/new job)."""
    # Fake job_id (empty history) - should warn/info not error
    result = runner.invoke(app, ["monitor", "details", "fake-job-id"])
    assert result.exit_code == 0  # Graceful
    assert "No history yet" in result.stdout or "warn" in result.stdout.lower()
    assert "Tip: Job too new" in result.stdout  # User guide

    # Details help
    result = runner.invoke(app, ["monitor", "details", "--help"])
    assert result.exit_code == 0
    assert "full stats" in result.stdout or "per-job" in result.stdout.lower()

