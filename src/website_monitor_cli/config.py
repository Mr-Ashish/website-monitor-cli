"""Default configuration values for the website monitor CLI."""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Configuration for website monitoring."""

    # Default success HTTP status codes (2xx typically)
    success_status_codes: set[int] = field(
        default_factory=lambda: {200, 201, 202, 204}
    )
    # Default interval between checks in seconds (for monitor mode)
    check_interval: int = 60
    # Default HTTP timeout in seconds
    timeout: int = 10
    # User agent for requests to avoid blocking
    user_agent: str = "website-monitor-cli/0.1.0"

    # Background/daemon settings
    # Base dir for PID files, logs (for bg jobs)
    data_dir: str = field(default_factory=lambda: os.path.expanduser("~/.website-monitor"))
    # PID file prefix for jobs
    pid_file_prefix: str = "monitor-job"
    # Default log file for bg output (appends timestamped entries for history)
    log_file: str = "monitor.log"
    # Enable background by default? (CLI override)
    background: bool = False

    # History & stats settings (for multi-log entries over time; enables uptime/avg in status)
    # Max log entries to retain per job (trim old for performance)
    max_log_entries: int = 100
    # Log rotate interval in seconds (e.g., daily; creates timestamped logs if hit)
    # 0 = disabled (single append-only log)
    log_rotate_interval: int = 86400  # 24h