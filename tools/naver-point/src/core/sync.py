"""Google Drive and local session synchronization module."""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from core.config import (
    SESSION_FILENAME,
    GOOGLE_DRIVE_SUBDIR,
    get_google_drive_mount_dir,
    get_default_session_path,
)

logger = logging.getLogger(__name__)


def is_gog_available() -> bool:
    """Check if gog CLI is installed and in PATH."""
    return shutil.which("gog") is not None


def find_drive_file_id_via_gog(filename: str = SESSION_FILENAME) -> str | None:
    """Use gog CLI to search for the session file in Google Drive."""
    if not is_gog_available():
        return None
    try:
        cmd = ["gog", "drive", "search", f"name = '{filename}' and trashed = false", "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            # data can be a list or envelope with 'files'
            files = data if isinstance(data, list) else data.get("files", [])
            if files and len(files) > 0:
                return files[0].get("id")
    except Exception as e:
        logger.warning(f"Failed to search file via gog: {e}")
    return None


class SessionSyncManager:
    """Manages session synchronization between local and Google Drive."""

    def __init__(self, session_path: Path | None = None):
        if session_path:
            self.session_path = session_path
            self.mode = "custom"
        else:
            self.session_path, self.mode = get_default_session_path()

    def get_status(self) -> dict:
        """Return synchronization status information."""
        mount_dir = get_google_drive_mount_dir()
        has_local_mount = mount_dir is not None
        has_gog = is_gog_available()
        exists = self.session_path.exists()
        size = self.session_path.stat().st_size if exists else 0

        return {
            "session_path": str(self.session_path),
            "mode": self.mode,
            "exists": exists,
            "size_bytes": size,
            "google_drive_mount": str(mount_dir) if has_local_mount else None,
            "gog_available": has_gog,
        }

    def pull(self) -> bool:
        """
        Pull session from Google Drive.
        If using Google Drive mount: verify it exists in mount.
        If local mode and gog is available: download via gog.
        """
        # If running in gdrive_mount mode, it's already directly on Google Drive Desktop!
        if self.mode == "gdrive_mount":
            return self.session_path.exists()

        # If in local mode, attempt download via gog CLI
        if is_gog_available():
            file_id = find_drive_file_id_via_gog(SESSION_FILENAME)
            if file_id:
                try:
                    self.session_path.parent.mkdir(parents=True, exist_ok=True)
                    cmd = ["gog", "drive", "download", file_id, "--out", str(self.session_path), "--overwrite"]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    if proc.returncode == 0:
                        logger.info(f"Successfully pulled session from Google Drive via gog to {self.session_path}")
                        return True
                    else:
                        logger.warning(f"gog download failed: {proc.stderr}")
                except Exception as e:
                    logger.error(f"Error pulling session via gog: {e}")

        # Fallback to checking local session
        return self.session_path.exists()

    def push(self) -> bool:
        """
        Push session to Google Drive.
        If using Google Drive mount: file is already written directly to Google Drive mount.
        If in local mode and gog is available: upload or replace via gog.
        """
        if not self.session_path.exists():
            logger.warning(f"Cannot push: {self.session_path} does not exist.")
            return False

        # If already directly on Google Drive mount, push is automatic via OS sync daemon
        if self.mode == "gdrive_mount":
            logger.info("Session saved directly to Google Drive mount.")
            return True

        # If in local mode, check if we can copy to Google Drive mount or upload via gog
        mount_dir = get_google_drive_mount_dir()
        if mount_dir:
            try:
                dest_dir = mount_dir / GOOGLE_DRIVE_SUBDIR
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / SESSION_FILENAME
                shutil.copy2(self.session_path, dest_path)
                logger.info(f"Copied session to Google Drive mount: {dest_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to copy to Google Drive mount: {e}")

        # If mount not present, use gog CLI
        if is_gog_available():
            file_id = find_drive_file_id_via_gog(SESSION_FILENAME)
            try:
                if file_id:
                    cmd = ["gog", "drive", "upload", str(self.session_path), "--replace", file_id]
                else:
                    cmd = ["gog", "drive", "upload", str(self.session_path), "--name", SESSION_FILENAME]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                if proc.returncode == 0:
                    logger.info("Successfully pushed session to Google Drive via gog.")
                    return True
                else:
                    logger.warning(f"gog upload failed: {proc.stderr}")
            except Exception as e:
                logger.error(f"Error pushing session via gog: {e}")

        return False

    def delete(self) -> bool:
        """Delete local session file and cloud file if possible."""
        deleted = False
        if self.session_path.exists():
            self.session_path.unlink()
            deleted = True

        mount_dir = get_google_drive_mount_dir()
        if mount_dir:
            cloud_file = mount_dir / GOOGLE_DRIVE_SUBDIR / SESSION_FILENAME
            if cloud_file.exists():
                cloud_file.unlink()
                deleted = True

        return deleted
