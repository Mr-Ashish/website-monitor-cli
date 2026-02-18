"""Core logic for URL validation and website status checking.

Uses stdlib urllib to avoid additional dependencies.
"""

import time
from http import HTTPStatus
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from typing import Any

from .config import Config


def is_valid_url(url: str) -> bool:
    """Validate if the provided string is a well-formed HTTP/HTTPS URL.

    Checks scheme (http/https) and netloc. Accepts localhost, IPs, etc.
    (Relaxed for practical use; stricter if needed.)
    """
    try:
        result = urlparse(url)
        # Basic but practical: scheme + netloc present
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:  # broad catch for parse issues
        return False


def check_website(url: str, config: Config | None = None) -> dict[str, Any]:
    """Hit the URL and check response status.

    Returns dict with: url, status_code, success, response_time, error (if any).
    Uses config for timeout, user_agent, success codes.
    """
    if config is None:
        config = Config()

    if not is_valid_url(url):
        return {
            "url": url,
            "status_code": None,
            "success": False,
            "response_time": 0.0,
            "error": "Invalid URL",
        }

    # Prepare request with headers
    headers = {"User-Agent": config.user_agent}
    req = Request(url, headers=headers)

    start_time = time.time()
    try:
        with urlopen(req, timeout=config.timeout) as response:
            status_code = response.getcode()
            response_time = time.time() - start_time
            success = status_code in config.success_status_codes
            return {
                "url": url,
                "status_code": status_code,
                "success": success,
                "response_time": round(response_time, 3),
                "error": None,
            }
    except HTTPError as e:
        # HTTPError has code for 4xx/5xx
        response_time = time.time() - start_time
        status_code = e.code
        success = status_code in config.success_status_codes
        return {
            "url": url,
            "status_code": status_code,
            "success": success,
            "response_time": round(response_time, 3),
            "error": str(e),
        }
    except URLError as e:
        response_time = time.time() - start_time
        return {
            "url": url,
            "status_code": None,
            "success": False,
            "response_time": round(response_time, 3),
            "error": f"URL error: {e.reason}",
        }
    except Exception as e:  # timeout, connection etc.
        response_time = time.time() - start_time
        return {
            "url": url,
            "status_code": None,
            "success": False,
            "response_time": round(response_time, 3),
            "error": str(e),
        }


# Background job utilities (stdlib-based daemonization via subprocess/PID files)
# Enables running monitor as bg job + management (stop/status/logs); no extra deps.

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def ensure_data_dir(config: Config) -> Path:
    """Ensure data dir for PID/logs exists (from config.data_dir)."""
    data_dir = Path(config.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_job_id(url: str) -> str:
    """Generate unique job ID for bg monitor (based on URL + UUID)."""
    # Sanitize URL for filename
    safe_url = url.replace("://", "_").replace("/", "_").replace(".", "_")[:50]
    return f"{safe_url}_{uuid4().hex[:8]}"


def get_pid_file(config: Config, job_id: str) -> Path:
    """Path to PID file for job."""
    return ensure_data_dir(config) / f"{config.pid_file_prefix}_{job_id}.pid"


def get_log_file(config: Config, job_id: str) -> Path:
    """Path to log file for job output."""
    return ensure_data_dir(config) / f"{job_id}.log"


def list_jobs(config: Config) -> list[dict[str, Any]]:
    """List running bg jobs from PID files (checks if PID alive).

    Stdlib-only: posix uses kill(0) test; other OS mark as unknown/running.
    """
    data_dir = ensure_data_dir(config)
    jobs = []
    for pid_file in data_dir.glob(f"{config.pid_file_prefix}_*.pid"):
        try:
            job_data = json.loads(pid_file.read_text())
            pid = job_data["pid"]
            # Check if process alive (cross-platform, no extra deps)
            if os.name == "posix":
                try:
                    os.kill(pid, 0)  # No-op signal to test
                    running = True
                except OSError:
                    running = False
            else:
                running = True  # Fallback: assume running (can't easily check w/o deps)
            job_data["running"] = running
            jobs.append(job_data)
        except Exception:
            # Skip corrupt/missing
            pass
    return jobs


def start_background(url: str, config: Config) -> dict[str, Any]:
    """Start watch monitor as bg job using detached subprocess (nohup-like).

    Returns job info; logs to file, saves PID/job metadata.
    """
    if not is_valid_url(url):
        return {"error": "Invalid URL", "success": False}

    # Generate job_id here (parent); passed to child watch via --job-id to sync
    # (prevents mismatch bug where child re-generated UUID -> missing log/PID
    # files + empty entries[] in compute_job_stats/details/logs).
    job_id = get_job_id(url)
    log_file = get_log_file(config, job_id)
    pid_file = get_pid_file(config, job_id)

    # Build cmd to re-run watch without --background (to avoid re-daemon)
    # Use -m for module to work installed/editable
    # Pass --job-id (hidden) to ensure parent/child use same ID for logs/PID.
    cmd = [
        sys.executable,
        "-m",
        "website_monitor_cli.main",
        "monitor",
        "watch",
        url,
        "--interval",
        str(config.check_interval),
        "--timeout",
        str(config.timeout),
        "--job-id",
        job_id,  # Sync for bg daemon child
        # no --max-checks for ongoing bg
    ]

    # Detached: stdout/stderr to log , new session (daemonize)
    with open(log_file, "a") as log_f:
        process = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach
            # preexec_fn=os.setsid if posix
        )

    # Save job metadata
    job_data = {
        "job_id": job_id,
        "url": url,
        "pid": process.pid,
        "log_file": str(log_file),
        "pid_file": str(pid_file),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "interval": config.check_interval,
            "timeout": config.timeout,
        },
        "running": True,
    }
    pid_file.write_text(json.dumps(job_data, indent=2))

    return job_data


def resolve_job_id(identifier: str, config: Config) -> str:
    """Resolve input as job_id (str) or PID (str/int) to canonical job_id.

    Scans running/completed bg jobs via list_jobs() and PID files. Enables
    PID-based mgmt for logs/details/stop (e.g., 'monitor logs <pid>') while
    keeping job_id backward-compatible.

    Falls back to treating identifier as job_id if no PID match (e.g., dead
    jobs where PID file still exists by job_id).
    """
    # Try as PID first (int match)
    try:
        pid_int = int(identifier)
        for job in list_jobs(config):
            if job.get("pid") == pid_int:
                return job.get("job_id")
    except ValueError:
        pass  # Not numeric PID; fall through

    # Default/fallback: assume identifier is already job_id
    return identifier


def stop_job(identifier: str, config: Config) -> bool:
    """Stop bg job by job_id (from status) *or* PID.

    Resolves via resolve_job_id(); then stops via SIGTERM/SIGKILL.
    """
    # Resolve PID -> job_id if needed
    job_id = resolve_job_id(identifier, config)
    pid_file = get_pid_file(config, job_id)
    if not pid_file.exists():
        return False
    try:
        job_data = json.loads(pid_file.read_text())
        pid = job_data["pid"]
        # Graceful stop
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)  # Give time
        # Force if still alive
        os.kill(pid, 0)  # Test
        os.kill(pid, signal.SIGKILL)
        pid_file.unlink()  # Clean
        return True
    except Exception:
        # Clean dead
        if pid_file.exists():
            pid_file.unlink()
        return False


def get_job_logs(identifier: str, config: Config, lines: int = 20) -> str:
    """Tail recent logs from job's log file.

    Accepts job_id (from status) *or* PID (resolves via resolve_job_id()).
    Enables e.g. 'monitor logs <pid>'.
    """
    # Resolve PID -> job_id if provided
    job_id = resolve_job_id(identifier, config)
    log_file = get_log_file(config, job_id)
    if not log_file.exists():
        return "No logs found."
    # Simple tail
    with open(log_file) as f:
        return "".join(f.readlines()[-lines:])


# History/stats for multi-entry logs & status dashboard
# Enables tracking over time: append timestamped checks , compute uptime/avg etc.
# (Called from watch; parses JSONL logs; supports rotate/trim per config.)

from datetime import datetime
from statistics import mean  # stdlib for avg resp time


def log_check_result(
    result: dict[str, Any], log_file: Path, config: Config
) -> None:
    """Append timestamped check result as JSON line to log (for history).

    Trims to max_log_entries; basic rotate if interval exceeded (e.g., daily file).
    Ensures parseable data for stats (uptime, avg time, pings).
    """
    if result.get("success") is None:  # Skip invalid
        return

    # Timestamp for tracking over time
    now = datetime.now()
    entry = {
        "timestamp": now.timestamp(),
        "iso_time": now.isoformat(),
        **result,  # url, status_code, success, response_time, error
    }

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Basic rotate: if file old > interval , rename to .YYYY-MM-DD
    if config.log_rotate_interval > 0 and log_file.exists():
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        if (now - mtime).total_seconds() > config.log_rotate_interval:
            rotated = log_file.with_suffix(f".{mtime.strftime('%Y-%m-%d')}")
            if not rotated.exists():
                log_file.rename(rotated)
            # New log continues

    # Append JSONL
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Trim old entries to max (keep recent for perf)
    if log_file.exists() and config.max_log_entries > 0:
        lines = log_file.read_text().splitlines()
        if len(lines) > config.max_log_entries:
            # Keep last N
            log_file.write_text("\n".join(lines[-config.max_log_entries:]) + "\n")


def compute_job_stats(identifier: str, config: Config) -> dict[str, Any]:
    """Compute cumulated stats from job's log history + metadata (for details dashboard).

    Accepts job_id *or* PID (resolves via resolve_job_id()).

    Returns enriched dict for dashboard:
    - start_time (pref PID file, fallback logs), next_run_time, uptime_pct (from start),
    - total_pings (=total_checks), failures (=total-successes), URL (from logs/PID).
    - Other: avg_resp, last_ping, success_count, period, etc.
    Fixed data flow for URL (even post-stop, no PID file) + error details.
    Enables full cumulated details dashboard in UI.
    """
    # Resolve PID -> job_id if provided
    job_id = resolve_job_id(identifier, config)

    # Load job metadata from PID file (for start_time/URL; note: unlinked on stop)
    pid_file = get_pid_file(config, job_id)
    job_data = {}
    if pid_file.exists():
        try:
            job_data = json.loads(pid_file.read_text())
        except json.JSONDecodeError:
            pass

    # Logs for history/stats (pings, uptime, failures; *always* has URL in entries)
    # Robust parse: skip empty/corrupt (fixes cases where trim/rotate/partial write
    # left bad lines; ensures entries populated when log/PID files exist).
    log_file = get_log_file(config, job_id)
    entries = []
    if log_file.exists():
        for line in log_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue  # Skip empty (e.g., from trim)
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # Skip corrupt

    if not entries:
        # Graceful for new/empty: return PID metadata + explicit error for UI
        # (PID may be absent post-stop, but error details passed through)
        # Durations=0 for format helpers
        return {
            "error": "Empty history (no checks logged yet)",
            "total_checks": 0,
            "start_time": job_data.get("started_at"),
            "job_id": job_id,
            "url": job_data.get("url"),  # PID fallback
            # Readable durations
            "time_since_start_seconds": 0,
            "next_run_in_seconds": 0,
            # Full error preserved for dashboard warn
        }

    # Cumulated stats calc (from start; URL always from logs entries for reliability)
    total = len(entries)  # = total_pings
    successes = sum(1 for e in entries if e.get("success"))
    failures = total - successes
    uptime_pct = round((successes / total) * 100, 2) if total else 0.0
    resp_times = [e.get("response_time", 0) for e in entries if e.get("response_time")]
    avg_resp = round(mean(resp_times), 3) if resp_times else 0.0

    # Times/pings; URL from first log entry (persists even if PID file deleted on stop)
    timestamps = sorted(e.get("timestamp", 0) for e in entries)
    last_ping = datetime.fromtimestamp(timestamps[-1]).isoformat() if timestamps else None
    # Next run est. = last + interval (from job config or default)
    interval = entries[-1].get("config", {}).get("interval", config.check_interval) if entries else config.check_interval
    next_run_time = (
        datetime.fromtimestamp(timestamps[-1] + interval).isoformat()
        if timestamps
        else None
    )
    # Period from first log
    period_start = datetime.fromtimestamp(timestamps[0]).isoformat() if timestamps else None
    period_end = last_ping
    # URL: prefer logs (reliable post-stop), fallback PID metadata
    url_from_logs = entries[0].get("url") if entries else None

    # For user-friendly display: calc durations (seconds since start, to next run)
    # (Used in UI format_duration; timestamps kept ISO for parse, but deltas humanized)
    now_ts = datetime.now().timestamp()
    start_ts = timestamps[0] if timestamps else None
    time_since_start = (now_ts - start_ts) if start_ts else 0
    next_in_seconds = (timestamps[-1] + interval - now_ts) if timestamps else 0

    return {
        # Cumulated dashboard fields (as requested; fixed data flow)
        "start_time": job_data.get("started_at") or period_start,
        "next_run_time": next_run_time,
        "uptime_pct": uptime_pct,  # From start
        "total_pings": total,  # = total_checks
        "success_count": successes,
        "failures": failures,  # Added
        # Readable durations (for dashboard)
        "time_since_start_seconds": time_since_start,
        "next_run_in_seconds": max(0, next_in_seconds),  # No negative
        # Existing/enriched
        "avg_response_time": avg_resp,
        "last_ping": last_ping,
        "period_start": period_start,
        "period_end": period_end,
        "total_checks": total,
        "job_id": job_id,  # For UI
        "url": url_from_logs or job_data.get("url"),  # Fixed: logs priority
    }
