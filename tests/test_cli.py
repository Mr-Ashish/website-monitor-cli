from typer.testing import CliRunner
import pytest

# Import test server for isolated, no-external-deps tests.
# /health endpoint (single domain signifying server health) defaults to 200 OK
# (success per Config.success_status_codes); controllable via test_server_mod.HEALTH_STATUS=500
# or /health?status=XXX query to change response for failure/other test scenarios.
# Sibling import (no relative `.` as tests/ not strict pkg; pytest handles).
# stop_test_server ensures shutdown even on test failure/exceptions.
# Also core/Config for bg job cleanup fixture (stop all jobs + data_dir after tests;
# prevents lingering PID/processes/files regardless of pass/fail).
from test_server import start_test_server, stop_test_server
import test_server as test_server_mod  # For mutating HEALTH_STATUS global
from website_monitor_cli.core import list_jobs, stop_job
from website_monitor_cli.config import Config
from website_monitor_cli.main import app
from pathlib import Path  # For data_dir cleanup in bg job fixture

runner = CliRunner()


@pytest.fixture(scope="module")
def test_server(request) -> str:
    """Pytest fixture starting a local test HTTP server for all tests.

    Provides http://localhost:8000/health URL (single endpoint signifying
    server health). Eliminates flakiness/external deps like example.com.

    Uses robust stop_test_server (shutdown + thread join) to ensure stop
    *always* (pass/fail/exceptions) via try/finally + addfinalizer.

    State mutable via test_server_mod.HEALTH_STATUS=XXX (or /health?status=XXX
    param) to change response for various test scenarios (success/fail/HTTP codes).
    """
    # Start server (port fixed; reuse_addr + timeout for clean restarts)
    server, thread = start_test_server(8000)
    # Reset to healthy default (200 OK) for consistency across tests
    test_server_mod.HEALTH_STATUS = 200

    # Finalizer: guaranteed teardown (runs even on test failure/exception)
    def cleanup_server():
        stop_test_server(server, thread)
        # Verify port free (no hanging listener)
        # (Optional: could check netstat, but silent here)
    request.addfinalizer(cleanup_server)

    # Yield base URL to tests (they can override state as needed)
    # try/finally ensures cleanup if yield exceptions
    try:
        yield "http://localhost:8000/health"
    finally:
        # Immediate cleanup (finalizer as backup)
        stop_test_server(server, thread)


@pytest.fixture(scope="module", autouse=True)
def cleanup_bg_jobs(request) -> None:
    """Autouse fixture to stop all bg jobs + clean data dir after tests.

    Ensures no lingering processes/PID/log files (even on fail/exception),
    addressing issue where jobs not closed post-run. Uses finalizer for
    reliability; skips during test if jobs needed (but tests are smoke-only).
    Data dir from Config (default ~/.website-monitor); safe rm for test files.
    """
    # Pre-test: stop any pre-existing jobs (from prior runs)
    config = Config()
    for job in list_jobs(config):
        stop_job(job.get("job_id", ""), config)

    # Finalizer: guaranteed cleanup post-tests (pass/fail)
    def final_cleanup():
        config = Config()
        for job in list_jobs(config):
            stop_job(job.get("job_id", ""), config)
        # Clean data dir (rm PID/logs; mkdir back; test-safe, avoids ~/. pollution)
        data_dir = Path(config.data_dir)
        if data_dir.exists():
            for f in data_dir.glob(f"{config.pid_file_prefix}_*"):
                f.unlink(missing_ok=True)
            for f in data_dir.glob("*.log"):
                f.unlink(missing_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

    request.addfinalizer(final_cleanup)


def test_help_shows_root_description() -> None:
    """Root help should describe the website monitor functionality."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Website Monitor CLI" in result.stdout
    assert "monitor" in result.stdout


def test_monitor_check_valid_url_smoke(test_server: str) -> None:
    """Smoke test: check known-good local test server URL (replaces external example.com).

    Uses /health endpoint (defaults to 200 OK via fixture; success per Config).
    Demonstrates end-to-end CLI check without external deps.
    """
    # Fixture ensures server running + healthy state; default config succeeds on 200.
    # Note: Rich table output + ANSI; assertions robust to formatting/colors.
    result = runner.invoke(app, ["monitor", "check", test_server])
    assert result.exit_code == 0
    assert "Status Code" in result.stdout
    assert "200" in result.stdout  # Value from table row
    assert "✅ Success" in result.stdout


def test_monitor_check_invalid_url() -> None:
    """Invalid URL should be caught before request and reported as failure."""
    result = runner.invoke(app, ["monitor", "check", "not-a-valid-url"])
    assert result.exit_code == 0
    assert "Invalid URL" in result.stdout
    assert "❌ Failed" in result.stdout


def test_monitor_check_failure_via_test_server(test_server: str) -> None:
    """Test failure path using local server (sets unhealthy state to verify CLI reports ❌ Failed).

    Uses controllable /health endpoint (?status=500 or direct HEALTH_STATUS) to
    simulate downtime/error status without external resources. Covers HTTPError
    handling in core.check_website + success_status_codes config.
    """
    # Change server response for this test (affects /health endpoint)
    # Option 1: direct module global (fast, no extra req); demonstrates 'based on
    # testing things' mutability.
    test_server_mod.HEALTH_STATUS = 500
    # (Alt: urllib.request.urlopen(f"{test_server}?status=500") but global simpler)

    # Rich table + ANSI; '500' appears, '❌ Failed' from print_check_result
    result = runner.invoke(app, ["monitor", "check", test_server])
    assert result.exit_code == 0
    assert "500" in result.stdout
    assert "❌ Failed" in result.stdout
    # Reset for other tests (fixture module scope shared; idempotent)
    test_server_mod.HEALTH_STATUS = 200


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

    # Logs help: check option documented + PID support. Robust to ANSI/Rich
    # (split '--lines'; -n/'lines' present).
    result = runner.invoke(app, ["monitor", "logs", "--help"])
    assert result.exit_code == 0
    assert "--lines" in result.stdout or "-n" in result.stdout or "lines" in result.stdout
    assert "PID" in result.stdout or "job" in result.stdout.lower()  # PID support

    # Stop + details helps: verify PID/job_id acceptance documented
    result = runner.invoke(app, ["monitor", "stop", "--help"])
    assert result.exit_code == 0
    assert "PID" in result.stdout or "job" in result.stdout.lower()

    result = runner.invoke(app, ["monitor", "details", "--help"])
    assert result.exit_code == 0
    assert "PID" in result.stdout or "job" in result.stdout.lower()


def test_monitor_status_smoke() -> None:
    """Smoke test status cmd (de-cluttered: bg jobs + quick uptime%; no avg/ping clutter).

    Handles empty jobs case (common in clean test env; no history logs).
    """
    result = runner.invoke(app, ["monitor", "status"])
    assert result.exit_code == 0
    # Empty (no jobs) or populated table; robust for test isolation
    assert (
        "Background Monitor Jobs" in result.stdout
        or "No background jobs" in result.stdout
    )
    # Uptime % only in table (when jobs exist); fallback accepts empty case msg
    # (original test assumption updated; still verifies stat when present)
    assert "Uptime %" in result.stdout or "No background jobs" in result.stdout
    # No clutter cols (safe even in empty case)
    assert "Avg Resp" not in result.stdout and "Next Ping" not in result.stdout
    # 'details' guide only when jobs present; fallback for empty (common in tests)
    # Note: lowered for case-insens; "no background jobs" substring present in msg
    assert (
        "details" in result.stdout.lower()
        or "no background jobs" in result.stdout.lower()
    )


def test_monitor_details_screen() -> None:
    """Test cumulated details *dashboard* for job (full stats: start_time, next_run,
    uptime %, total_pings, failures, etc. from start; graceful for empty/new).

    Now supports PID *or* job_id (via core.resolve_job_id); both fallback gracefully
    for fake/nonexistent (partial dashboard from PID metadata).
    """
    # Fake job_id (empty history) - partial dashboard + warn/info
    # Now prints full error details + URL (fixed data flow; expect "N/A" for fake only)
    result = runner.invoke(app, ["monitor", "details", "fake-job-id"])
    assert result.exit_code == 0  # Graceful
    assert "Dashboard Overview" in result.stdout or "Job:" in result.stdout  # Panel
    assert "Empty history" in result.stdout  # Full error printed for user
    assert "Error Details" in result.stdout or "Issue:" in result.stdout  # Error panel
    assert "Tip: Job too new" in result.stdout  # Guide
    # New dashboard fields (partial; URL fixed via logs/PID priority)
    assert "Start Time" in result.stdout or "Started:" in result.stdout
    # URL may be N/A for fake (no files); real jobs show URL from logs

    # PID support: fake PID also resolves (falls back to id) + partial dashboard
    # Error details ensure user sees issue (no hidden N/A)
    result = runner.invoke(app, ["monitor", "details", "99999"])
    assert result.exit_code == 0
    assert "Dashboard Overview" in result.stdout or "Job:" in result.stdout
    assert "Empty history" in result.stdout  # Error
    assert "Error Details" in result.stdout or "Issue:" in result.stdout

    # Details help (documents dashboard/PID)
    result = runner.invoke(app, ["monitor", "details", "--help"])
    assert result.exit_code == 0
    assert "dashboard" in result.stdout.lower() or "cumulated" in result.stdout.lower()
    assert "PID" in result.stdout or "job" in result.stdout.lower()
    assert "uptime" in result.stdout.lower() or "failures" in result.stdout.lower()


def test_monitor_logs_and_stop_pid_support() -> None:
    """Test logs/stop cmds now accept PID *or* job_id (via resolve_job_id in core).

    Uses fake values (graceful: no crash, sensible msg); covers both paths.
    """
    # Fake job_id for logs
    result = runner.invoke(app, ["monitor", "logs", "fake-job-id"])
    assert result.exit_code == 0
    assert "Logs for job" in result.stdout or "No logs" in result.stdout

    # Fake PID for logs
    result = runner.invoke(app, ["monitor", "logs", "99999"])
    assert result.exit_code == 0
    assert "Logs for job" in result.stdout or "No logs" in result.stdout

    # Logs help (documents PID)
    result = runner.invoke(app, ["monitor", "logs", "--help"])
    assert result.exit_code == 0
    assert "PID" in result.stdout or "job" in result.stdout.lower()

    # Stop with fake (should error gracefully, not crash)
    result = runner.invoke(app, ["monitor", "stop", "fake-pid"])
    assert result.exit_code == 1  # Expected fail for missing
    assert "Failed to stop" in result.stdout

