"""
Job Scout — Web Server
Serves the jobs dashboard and provides an API to trigger background scraping.

Usage:
    python server.py                  # Start on port 5000
    python server.py --port 8080      # Custom port
"""

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from tools.file_handler import load_career_pages
from tools.job_store import init_db, get_new_jobs, mark_seen, get_seen_count


# ── Shared State ──────────────────────────────────────────────
class ScraperState:
    """Thread-safe state for tracking scraper status."""

    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        self.last_refresh = None
        self.last_job_count = 0
        self.last_error = None
        self.last_errors = []

    def start(self):
        with self._lock:
            self.running = True
            self.last_error = None
            self.last_errors = []

    def finish(self, job_count: int, new_job_count: int, errors: list):
        with self._lock:
            self.running = False
            self.last_refresh = datetime.now(timezone.utc).isoformat()
            self.last_job_count = job_count
            self.last_new_job_count = new_job_count
            self.last_errors = errors

    def fail(self, error: str):
        with self._lock:
            self.running = False
            self.last_error = error

    def to_dict(self):
        with self._lock:
            return {
                "running": self.running,
                "last_refresh": self.last_refresh,
                "last_job_count": self.last_job_count,
                "last_new_job_count": getattr(self, 'last_new_job_count', self.last_job_count),
                "last_error": self.last_error,
                "last_errors": self.last_errors,
                "seen_count": get_seen_count(settings.db_path),
            }


state = ScraperState()


# ── Background Scraper ────────────────────────────────────────
def run_scraper_background(config_path: str):
    """Run the scraping pipeline in a background thread."""
    from run import run_once

    state.start()
    print(f"\n🔄 [Server] Scraping started at {datetime.now().strftime('%H:%M:%S')}...")

    try:
        career_pages = load_career_pages(config_path)
        final_jobs, errors = run_once(career_pages)

        total_count = len(final_jobs) if final_jobs else 0

        # Determine which jobs are new (not previously seen)
        new_jobs = get_new_jobs(final_jobs, settings.db_path) if final_jobs else []
        new_count = len(new_jobs)

        # Build a set of dedup keys for new jobs (for badging in HTML)
        new_keys = set()
        for job in new_jobs:
            title = job.get("title", "").lower().strip()
            company = job.get("company", "").lower().strip()
            location = job.get("location", "").lower().strip()
            new_keys.add(f"{title}|{company}|{location}")

        # Mark all scraped jobs as seen
        if final_jobs:
            mark_seen(final_jobs, settings.db_path)

        # Generate HTML with ALL 2-day jobs, tagging new ones for the banner
        if final_jobs:
            from tools.html_report import generate_html_report
            import os
            html_path = os.path.join(settings.output_dir, "jobs.html")
            generate_html_report(final_jobs, html_path, new_keys=new_keys)

        state.finish(total_count, new_count, errors or [])
        print(f"✅ [Server] Scraping complete: {total_count} total, {new_count} new jobs.")

        if errors:
            print(f"⚠️  [Server] {len(errors)} error(s) during scraping.")

    except Exception as e:
        state.fail(str(e))
        print(f"❌ [Server] Scraping failed: {e}")


# ── HTTP Handler ──────────────────────────────────────────────
class ReusableHTTPServer(HTTPServer):
    """HTTPServer that allows port reuse to avoid 'Address already in use' errors."""
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        """Silently ignore client disconnects (BrokenPipe) — normal with status polling."""
        import sys
        if sys.exc_info()[0] in (BrokenPipeError, ConnectionResetError):
            return  # Client closed the connection early — not a real error
        super().handle_error(request, client_address)


class JobScoutHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for Job Scout web server."""

    config_path = "config/career_pages.yaml"

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_jobs_html()
        elif self.path == "/api/status":
            self._json_response(state.to_dict())
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/refresh":
            self._handle_refresh()
        elif self.path == "/api/reset":
            self._handle_reset()
        else:
            self.send_error(404, "Not Found")

    def _serve_jobs_html(self):
        """Serve the generated jobs HTML report (already has its own refresh button)."""
        html_path = os.path.join(settings.output_dir, "jobs.html")

        if not os.path.exists(html_path):
            # No report yet — serve a welcome page
            self._serve_welcome_page()
            return

        with open(html_path, "r") as f:
            content = f.read()

        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_welcome_page(self):
        """Serve a simple page when no jobs report exists yet."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Scout</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif;
      background: #0f0f13; color: #e0e0e0;
      display: flex; justify-content: center; align-items: center;
      height: 100vh;
    }
    .container { text-align: center; }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; }
    h1 span { color: #6366f1; }
    p { color: #9ca3af; margin-bottom: 2rem; }
    .btn {
      background: linear-gradient(135deg, #6366f1, #4f46e5);
      color: #fff; border: none; padding: 0.8rem 2rem;
      border-radius: 8px; font-size: 1rem; cursor: pointer;
      transition: all 0.2s; font-weight: 600;
    }
    .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(99,102,241,0.4); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; box-shadow: none; }
    .status { margin-top: 1.5rem; color: #9ca3af; font-size: 0.9rem; min-height: 1.5em; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #6366f1;
      border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite;
      vertical-align: middle; margin-right: 8px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔍 <span>Job Scout</span></h1>
    <p>No jobs report found yet. Click below to start your first scrape!</p>
    <button class="btn" onclick="startRefresh(this)">🚀 Fetch Jobs</button>
    <div class="status" id="status"></div>
  </div>
  <script>
    function startRefresh(btn) {
      btn.disabled = true;
      document.getElementById('status').innerHTML = '<span class="spinner"></span> Scraping in progress...';
      fetch('/api/refresh', { method: 'POST' })
        .then(r => r.json())
        .then(() => pollStatus())
        .catch(e => {
          document.getElementById('status').textContent = '❌ Error: ' + e.message;
          btn.disabled = false;
        });
    }
    function pollStatus() {
      const poll = setInterval(() => {
        fetch('/api/status').then(r => r.json()).then(data => {
          if (!data.running) {
            clearInterval(poll);
            if (data.last_error) {
              document.getElementById('status').textContent = '❌ ' + data.last_error;
            } else {
              document.getElementById('status').textContent = '✅ Done! Reloading...';
              setTimeout(() => window.location.reload(), 500);
            }
          }
        });
      }, 2000);
    }
  </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _handle_refresh(self):
        """Start a scraping job in the background."""
        if state.running:
            self._json_response(
                {"status": "already_running", "message": "A scrape is already in progress."},
                status=409,
            )
            return

        thread = threading.Thread(
            target=run_scraper_background,
            args=(self.config_path,),
            daemon=True,
        )
        thread.start()

        self._json_response({"status": "started", "message": "Scraping started in background."})

    def _handle_reset(self):
        """Clear the seen-jobs database so next scrape shows all jobs as new."""
        if state.running:
            self._json_response(
                {"status": "busy", "message": "Cannot reset while a scrape is running."},
                status=409,
            )
            return

        try:
            from tools.job_store import _get_connection
            conn = _get_connection(settings.db_path)
            conn.execute("DELETE FROM seen_jobs")
            conn.commit()
            conn.close()

            # Also remove the existing HTML report so the welcome page shows
            html_path = os.path.join(settings.output_dir, "jobs.html")
            if os.path.exists(html_path):
                os.remove(html_path)

            print("[Server] \U0001f5d1\ufe0f  Seen-jobs database cleared. Ready for a fresh scrape.")
            self._json_response({"status": "ok", "message": "Seen jobs cleared. Run a refresh to see all fresh listings."})
        except Exception as e:
            self._json_response({"status": "error", "message": str(e)}, status=500)

    def _json_response(self, data: dict, status: int = 200):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default request logging (too noisy with polling)."""
        # Only log non-status requests
        if "/api/status" not in str(args[0]):
            super().log_message(format, *args)


# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Job Scout — Web Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to run the server on (default: 8080)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/career_pages.yaml",
        help="Path to career pages YAML config",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0 for network access)",
    )

    args = parser.parse_args()

    # Pass config path to handler
    JobScoutHandler.config_path = args.config

    # Check if config exists
    if not os.path.exists(args.config):
        print(f"❌ Config file not found: {args.config}")
        sys.exit(1)

    # Initialize job store DB
    init_db(settings.db_path)
    seen = get_seen_count(settings.db_path)

    server = ReusableHTTPServer((args.host, args.port), JobScoutHandler)

    print("=" * 60)
    print("  🔍 Job Scout — Web Server")
    print("=" * 60)
    print(f"  URL:    http://localhost:{args.port}")
    if args.host == "0.0.0.0":
        print(f"  LAN:    http://<your-ip>:{args.port}")
    print(f"  Config: {args.config}")
    print(f"  Output: {settings.output_dir}/")
    print(f"  Seen:   {seen} previously seen jobs in DB")
    print("=" * 60)
    print("  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⛔ Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
