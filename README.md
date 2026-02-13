# Website Monitor CLI Boilerplate

Starter template for building Python CLI tools with polished terminal UI using Typer + Rich.

## Features

- Clean command-group structure with Typer.
- Rich terminal UX primitives (panels, tables, status output).
- Built-in progress bar pattern for long-running commands.
- uv-compatible project setup in `pyproject.toml`.
- Test/lint/type-check defaults for day-1 quality gates.

## Quick Start

1. Create and sync the environment:

```bash
uv sync --all-groups
```

2. Run the CLI help:

```bash
uv run website-monitor --help
```

3. Run the demo command with progress bar:

```bash
uv run website-monitor demo run --total 25 --delay 0.02
```

## Run Without uv

You can install the CLI once and run `website-monitor` directly.

### Option 1: Local virtualenv install (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
website-monitor --help
website-monitor demo run --total 25 --delay 0.02
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
  cli_boilerplate/
    main.py
    commands/
      demo.py
    ui/
      console.py
tests/
  test_cli.py
```

## Add a New Command

1. Create a new module under `src/cli_boilerplate/commands/`.
2. Define a `typer.Typer()` app or command functions in that module.
3. Register it in `src/cli_boilerplate/main.py` with `app.add_typer(...)`.
4. Add tests in `tests/`.
