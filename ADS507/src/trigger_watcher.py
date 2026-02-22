"""
trigger_watcher.py — Event-based pipeline trigger.

Watches the data directory for new or modified CSV files.  When a change is
detected the full pipeline (run_pipeline.py) is executed automatically.

This satisfies the "triggered pipeline" requirement for a static dataset:
dropping a new (or updated) CSV into the watched folder fires the pipeline
exactly as a real LMS/SIS data-delivery event would.

Usage:
    python src/trigger_watcher.py

    # Or run in the background:
    nohup python src/trigger_watcher.py &

Stop with Ctrl-C (or kill the background process).
"""

import subprocess
import sys
import logging
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("trigger_watcher")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "open+university+learning+analytics+dataset"
PIPELINE_SCRIPT = ROOT / "src" / "run_pipeline.py"

# Minimum seconds between pipeline runs (debounce — avoids double-firing
# when a file-save generates multiple filesystem events).
DEBOUNCE_SECONDS = 5


class DataDirectoryHandler(FileSystemEventHandler):
    """Fire the pipeline when a CSV file is created or modified."""

    def __init__(self):
        self._last_run = 0.0

    def _should_trigger(self, path: str) -> bool:
        return path.endswith(".csv")

    def _trigger_pipeline(self, reason: str):
        now = time.time()
        if now - self._last_run < DEBOUNCE_SECONDS:
            log.debug("Debounce — skipping duplicate event (%s)", reason)
            return

        self._last_run = now
        log.info("TRIGGER fired: %s", reason)
        log.info("Starting pipeline: %s", PIPELINE_SCRIPT)

        result = subprocess.run(
            [sys.executable, str(PIPELINE_SCRIPT)],
            capture_output=False,   # let pipeline logs print to console
        )

        if result.returncode == 0:
            log.info("Pipeline completed successfully.")
        else:
            log.error("Pipeline exited with code %d — check logs above.", result.returncode)

    # ── Watchdog event hooks ──────────────────────────────────────────────────
    def on_created(self, event):
        if not event.is_directory and self._should_trigger(event.src_path):
            self._trigger_pipeline(f"new file: {event.src_path}")

    def on_modified(self, event):
        if not event.is_directory and self._should_trigger(event.src_path):
            self._trigger_pipeline(f"modified file: {event.src_path}")


def main():
    if not DATA_DIR.exists():
        log.error("Data directory not found: %s", DATA_DIR)
        sys.exit(1)

    handler = DataDirectoryHandler()
    observer = Observer()
    observer.schedule(handler, str(DATA_DIR), recursive=False)
    observer.start()

    log.info("Watching for CSV changes in: %s", DATA_DIR)
    log.info("Press Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down watcher.")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
