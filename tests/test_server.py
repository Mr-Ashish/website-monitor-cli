"""Simple test HTTP server for website-monitor-cli tests.

Eliminates external dependency (e.g., example.com) by providing a local
/health endpoint. The server state can be controlled (e.g., healthy=200 OK
or unhealthy=500) to test success/failure paths in CLI checks without
relying on external resources.

Uses only stdlib for no extra deps. Runs in thread for pytest fixtures.

Single endpoint: /health (signifies server health; query param ?status=XXX
changes response for testing scenarios).
"""

import http.server
import socketserver
import threading
import time  # For standalone keep-alive + sleep
from urllib.parse import urlparse, parse_qs
from typing import Tuple

# Global state for controllable health status (default healthy)
# Tests can update via /health?status=XXX or directly set this.
HEALTH_STATUS: int = 200


class HealthHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler exposing /health endpoint with mutable response.

    - GET /health           -> returns current HEALTH_STATUS (200/500/etc.)
    - GET /health?status=500 -> updates state then returns 200 (control API)
    - Other paths -> 404
    """

    def do_GET(self) -> None:
        """Handle GET; parse path/query to support health check + state change."""
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/health":
            # Support state change via query param for test flexibility
            # e.g., http://localhost:8000/health?status=500 simulates failure
            query_params = parse_qs(parsed_path.query)
            if "status" in query_params:
                global HEALTH_STATUS
                try:
                    HEALTH_STATUS = int(query_params["status"][0])
                except ValueError:
                    HEALTH_STATUS = 400  # Invalid status
                # Acknowledge change
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Health status set to {HEALTH_STATUS}".encode())
                return

            # Standard health response (uses current state)
            self.send_response(HEALTH_STATUS)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            if HEALTH_STATUS == 200:
                self.wfile.write(b"OK - server is healthy")
            else:
                self.wfile.write(b"ERROR - server is unhealthy")
        else:
            self.send_error(404, "Only /health endpoint supported")

    def log_message(self, format: str, *args: str) -> None:
        """Suppress server logs during tests to keep output clean."""
        pass  # Silent for pytest


def start_test_server(port: int = 8000) -> Tuple[socketserver.TCPServer, threading.Thread]:
    """Start the test server in a background thread.

    Returns (server, thread) for use in pytest fixtures.
    Uses TCPServer for simplicity; port reusable via SO_REUSEADDR.
    Thread *not* daemon by default for explicit shutdown control.
    """
    # Allow quick restart/reuse in tests (handles fixture restarts)
    socketserver.TCPServer.allow_reuse_address = True
    # Set timeout to unblock shutdown
    httpd = socketserver.TCPServer(("", port), HealthHandler)
    httpd.timeout = 0.5  # Short timeout for serve_forever to check shutdown

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = False  # Explicit control (join in stop)
    server_thread.start()
    return httpd, server_thread


def stop_test_server(server: socketserver.TCPServer, thread: threading.Thread) -> None:
    """Robustly stop the test server (shutdown, thread join, close).

    Ensures cleanup even if tests fail or exceptions occur (used in fixture
    + finalizer). Handles TCPServer/serve_forever quirks.
    """
    try:
        if server:
            server.shutdown()  # Signals serve_forever to exit
            server.server_close()  # Release socket/port
    except Exception:
        pass  # Ignore if already closed
    if thread and thread.is_alive():
        thread.join(timeout=2.0)  # Wait up to 2s; force stop if hangs


# Standalone run for manual testing/debug
if __name__ == "__main__":
    print("Starting test server at http://localhost:8000/health")
    print("Use ?status=500 to simulate failure; default=200 OK")
    server, thread = start_test_server()
    try:
        # Keep running until Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down test server...")
        stop_test_server(server, thread)
