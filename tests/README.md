# Running Test Cases for Website Monitor CLI

This directory contains tests for the CLI tool, now fully isolated from external dependencies (e.g., no reliance on `example.com`). A local test server (`test_server.py`) provides a controllable `/health` endpoint for simulating healthy/unhealthy states.

## Test Structure
- **`test_cli.py`**: CLI smoke/integration tests using Typer's `CliRunner`.
  - Covers help output, URL validation, success/failure checks, subcommands, bg job mgmt (status/stop/logs/details; now supports PID *or* job_id for logs/details/stop), and stats from history logs.
  - Uses `/health` for valid checks (200 OK) + mutable state for failure (e.g., 500).
- **`test_server.py`**: Very small stdlib-based HTTP server (as requested).
  - **Endpoint**: `http://localhost:8000/health` (signifies server health).
  - **Controllable responses**: Set `HEALTH_STATUS=500` or `?status=500` query to change output (e.g., for testing success/fail paths in `core.check_website()`).
  - Runs in daemon thread; pytest fixture auto-starts/stops it.
- **Pytest config**: In `pyproject.toml` (`testpaths = ["tests"]`, quiet mode).

Tests are independent, sequential by default (pytest discovery order), and pass reliably (`pytest tests/` succeeds).

## Running All Test Cases (Single Command)
Use the dedicated runner for one-command execution (sets up env, runs *all* tests in sequence, verifies):

```bash
# From repo root
tests/run_tests.sh
```

- **What it does**: Activates env, runs `pytest tests/ -q` (sequential, no parallel), shows summary.
- **Expected**: `........` (8 tests pass) + exit 0.
- **Server lifecycle**: Local test server (`/health`) auto-stops post-tests (fixture + finalizer; check `ss -tlnp | grep 8000`).
- **Bg jobs cleanup**: Autouse fixture + runner ensures all jobs stopped + data dir cleaned post-tests (pass/fail; no lingering PID/processes/files).
- Alt: `uv run pytest tests/` or `python -m pytest tests/`.
- Dev setup: `uv sync --all-groups` (includes pytest) or venv: `python3 -m venv .venv && . .venv/bin/activate && pip install -e . && pip install pytest`.

## Running Specific Tests
```bash
# All (sequential)
pytest tests/ -q

# Single test + verbose
pytest tests/test_cli.py::test_monitor_check_valid_url_smoke -q -v --tb=short

# With coverage
pytest tests/ --cov=src/website_monitor_cli --cov-report=term-missing

# Debug test server standalone
python tests/test_server.py  # Visit http://localhost:8000/health?status=500
```

## Test Server Details
- **Why?** Replaces external resources; `/health` changes response based on test needs (e.g., healthy=✅, unhealthy=❌).
- **Fixture** (`test_cli.py`): Module-scoped, yields URL, resets state (200 OK).
- **Customization**: Edit `HEALTH_STATUS` or extend handler for new scenarios.
- No deps; uses `http.server`, `threading`, etc.

## Notes
- Bg tests are smoke (no real jobs); check `~/.website-monitor/` for artifacts.
- Rich/ANSI output: Asserts are robust to formatting.
- Lint/typecheck: `uv run ruff check .` + `uv run mypy src`.
- All tests pass; server ensures reliability.

For issues, inspect `test_server.py` or rerun with `--log-cli-level=DEBUG`.
