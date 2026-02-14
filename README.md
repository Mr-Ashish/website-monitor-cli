# Website Monitor CLI

A CLI tool to monitor websites: validate URLs, perform HTTP checks, and continuously monitor availability based on response status codes. Uses default config for check interval, success status codes (e.g., 200, 201), timeout, etc. Built with Typer + Rich for polished UX.

## Features

- URL validation before requests.
- HTTP status checks using stdlib (configurable success codes like 2xx).
- Default config values: check_interval=60s, success_status_codes={200,201,202,204}, timeout=10s + bg settings (PID/logs dirs).
- Single `check`, `watch` (fg/bg daemon) for monitoring.
- Bg job management: `status`, `stop <job-id>`, `logs <job-id>` (detached via subprocess/PID files).
- Rich tables for checks/jobs/logs; root --help epilog with copyable samples.
- **All options explicitly documented** in CLI --help (e.g., --timeout, --interval, --background/-b) .
- Clean Typer structure, uv/pip setup, tests/lint/typecheck.

## Quick Start

1. Create and sync the environment:

```bash
uv sync --all-groups
```

2. Run the CLI help (shows all options):

```bash
uv run website-monitor --help
```

3. Check a website (uses default config):

```bash
uv run website-monitor monitor check https://example.com
```

4. Monitor continuously (every 60s by default; Ctrl+C to stop):

```bash
uv run website-monitor monitor watch https://example.com --interval 30 --max-checks 5
```

## Run Without uv

You can install the CLI once and run `website-monitor` directly.

### Option 1: Local virtualenv install (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
website-monitor --help
website-monitor monitor check https://example.com
```

### Option 2: Global command with pipx

```bash
pipx install .
website-monitor --help
```

## Development Commands

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Project Layout

```text
src/
  website_monitor_cli/
    main.py          # CLI entrypoint (+ epilog samples)
    commands/
      monitor.py     # check/watch (+--background), status/stop/logs (bg mgmt)
    config.py        # Defaults (interval, status codes, + bg: data_dir/PID/logs)
    core.py          # Validation/checks + bg utils (start_background, list_jobs etc.)
    ui/
      console.py     # Rich helpers (check/jobs/logs tables)
tests/
  test_cli.py
```

## Usage Examples

- Quick check: `website-monitor monitor check <url> --timeout 5`
- Continuous monitor (fg): `website-monitor monitor watch <url> --interval 30`
- Bg daemon job: `website-monitor monitor watch <url> --background` (starts detached; check `status`)
- Manage bg: `website-monitor monitor status` (quick uptime%) , `details <job-id>` (full stats: avg resp, pings etc.), `logs` / `stop`
- Only valid URLs proceed; success by config status codes; bg uses ~/.website-monitor/ for PID/logs/history (multi-entry over time).
- Override defaults via CLI options (fully documented in --help).

## CLI Help & Options

Typer auto-generates help (docstrings + `help=` params), with root epilog for samples. All options (incl. bg) visible:

```bash
# Root help (incl. epilog samples for copy-paste)
$ website-monitor --help
# ...
# **Quick Start Examples** (copy and run these):
# - Single check: `...`
# - ... background job: `website-monitor monitor watch ... --background`
# - Manage: `monitor status` / `logs` / `stop`

# Monitor group help (now incl. bg cmds)
$ website-monitor monitor --help
# Subcommands: check, watch, status, stop, logs

# Watch (with bg option)
$ website-monitor monitor watch --help
# ...
# Options:
#   ...
#   --background, -b     Run as background daemon job (uses PID/log files...
#   ...

# Other manager help (status now shows stats from history)
$ website-monitor monitor status --help
# Lists bg jobs + dashboard stats: uptime%, avg resp time, last/next ping, checks
# (computed from multiple timestamped log entries over time)
$ website-monitor monitor logs <job-id> --lines 50
```

This + epilog ensures users see/copy defaults, overrides, bg capability, config options (interval/status codes). Full details in code/docs.

## Development

The structure supports easy extension:
- Config/bg in `config.py`/`core.py` (stdlib daemon via subprocess/PID).
- Commands in `commands/monitor.py` (check/watch/bg mgr with explicit help=), registered in `main.py`.
- UI in `console.py`; tests in `tests/`. (Bg data: ~/.website-monitor/)
