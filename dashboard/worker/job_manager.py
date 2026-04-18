"""In-process background job manager."""

from __future__ import annotations

import threading

from config import Settings

from dashboard.db.session import AdminDatabase
from dashboard.worker.job_runner import execute_run_job


class JobManager:
    """Starts background threads for queued runs."""

    def __init__(self, admin_db: AdminDatabase, base_settings: Settings) -> None:
        self._admin_db = admin_db
        self._base_settings = base_settings
        self._threads: dict[int, threading.Thread] = {}

    def start_run(self, run_id: int) -> None:
        """Start a background thread for a run if it is not already active."""
        existing = self._threads.get(run_id)
        if existing is not None and existing.is_alive():
            return

        thread = threading.Thread(
            target=execute_run_job,
            args=(run_id, self._admin_db, self._base_settings),
            daemon=True,
            name=f"run-job-{run_id}",
        )
        self._threads[run_id] = thread
        thread.start()
