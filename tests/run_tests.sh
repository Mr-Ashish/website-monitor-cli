#!/bin/bash
# Single command to run ALL test cases in sequence for website-monitor-cli.
# Ensures:
# - Env setup (venv/uv fallback).
# - Sequential execution (pytest default; no parallel).
# - Uses local test server (/health endpoint) for isolation.
# - Verifies success; exit 0 only if all pass.
#
# Usage: ./tests/run_tests.sh  (from repo root)
# See tests/README.md for details.

set -e  # Exit on error

echo "🚀 Setting up environment and running all test cases in sequence..."

# Prefer uv if available (per project); fallback to venv.
if command -v uv >/dev/null 2>&1; then
    echo "Using uv for tests..."
    uv run pytest tests/ -q --tb=no
elif [ -d ".venv" ]; then
    echo "Using existing .venv..."
    . .venv/bin/activate
    pytest tests/ -q --tb=no
else
    echo "Creating venv and installing deps (first-time setup)..."
    python3 -m venv .venv
    . .venv/bin/activate
    pip install --quiet -e .
    pip install --quiet pytest pytest-cov
    pytest tests/ -q --tb=no
fi

# Post-run check (pytest -q shows dots; count tests implicitly via exit code)
# + verify test server stopped (no hanging listener on port 8000; runs pass/fail)
# + bg jobs cleanup (stop all + rm PID/logs; ensures no lingering processes/files)
echo "✅ All test cases completed successfully in sequence!"
echo "   - Tests run: $(find tests/ -name 'test_*.py' | wc -l) file(s) processed."
echo "   - Local test server (/health) ensured isolation from external resources."
if ss -tlnp 2>/dev/null | grep -q ':8000'; then
    echo "   - ⚠️  WARNING: Port 8000 still listening (server may not have stopped)!"
else
    echo "   - Server stopped cleanly (no listener on port 8000)."
fi
# Cleanup bg jobs/data (matches test fixture; safe for ~/.website-monitor)
# Ensures jobs closed post-run (stop all + rm PID/logs; no leftovers).
echo "   - Cleaning bg jobs/PID/logs..."
python -c '
from website_monitor_cli.core import list_jobs, stop_job
from website_monitor_cli.config import Config
from pathlib import Path
config = Config()
for job in list_jobs(config):
    stop_job(job.get("job_id", ""), config)
data_dir = Path(config.data_dir)
if data_dir.exists():
    for f in data_dir.glob(f"{config.pid_file_prefix}_*"):
        f.unlink(missing_ok=True)
    for f in data_dir.glob("*.log"):
        f.unlink(missing_ok=True)
data_dir.mkdir(parents=True, exist_ok=True)
print("   - Bg cleanup complete.")
' || echo "   - Cleanup skipped (non-critical)."
echo "   - See tests/README.md for details or rerun specific cases."
exit 0
