"""In-process background job manager."""

from __future__ import annotations

import subprocess
import sys

from config import Settings

from dashboard.db.session import AdminDatabase


class JobManager:
    """Starts background subprocesses for queued runs."""

    def __init__(self, admin_db: AdminDatabase, base_settings: Settings) -> None:
        self._admin_db = admin_db
        self._base_settings = base_settings
        self._processes: dict[int, subprocess.Popen[bytes]] = {}

    def start_run(self, run_id: int) -> None:
        """Start a background subprocess for a run if it is not already active."""
        existing = self._processes.get(run_id)
        if existing is not None and existing.poll() is None:
            return

        command = [
            sys.executable,
            "-c",
            (
                "from dashboard.worker.job_runner import execute_run_job_subprocess; "
                f"execute_run_job_subprocess({run_id}, {str(self._admin_db.database_path)!r})"
            ),
        ]
        process = subprocess.Popen(
            command,
            cwd=str(self._base_settings.base_dir),
        )
        self._processes[run_id] = process
