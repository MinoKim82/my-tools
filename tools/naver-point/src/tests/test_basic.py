"""Basic tests for naver-point configuration and sync manager."""

import pytest
from pathlib import Path
from core.config import (
    SESSION_FILENAME,
    GOOGLE_DRIVE_SUBDIR,
    get_default_session_path,
    get_google_drive_mount_dir,
)
from core.sync import SessionSyncManager, is_gog_available


def test_config_paths():
    """Verify default session resolution and file name."""
    session_path, mode = get_default_session_path()
    assert session_path.name == SESSION_FILENAME
    assert mode in ["env", "gdrive_mount", "local"]


def test_sync_manager_status():
    """Verify sync manager returns valid status schema."""
    manager = SessionSyncManager()
    status = manager.get_status()

    assert "session_path" in status
    assert "mode" in status
    assert "exists" in status
    assert "google_drive_mount" in status
    assert "gog_available" in status
    assert isinstance(status["exists"], bool)
    assert isinstance(status["gog_available"], bool)


def test_gog_detection():
    """Verify gog detection returns a boolean."""
    res = is_gog_available()
    assert isinstance(res, bool)
