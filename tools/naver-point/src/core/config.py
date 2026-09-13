"""Configuration settings and path resolver for naver-point."""

import os
import glob
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# URLs
NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_PAY_BENEFIT_URL = "https://point.pay.naver.com/pc/main"
NAVER_CAMPAIGN_URL = "https://m-campaign.naver.com/npay/gorandomp/?rcode=offpay"

# File names
SESSION_FILENAME = "naver_point_session.json"
GOOGLE_DRIVE_SUBDIR = Path("my-tools") / "naver-point"

# Logging & Debug
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "naver_point.log"
ERROR_SCREENSHOT_PATH = LOGS_DIR / "error_screenshot.png"

# Standard Local OS Path (~/.local/share/naver-point)
DEFAULT_LOCAL_DATA_DIR = Path.home() / ".local" / "share" / "naver-point"


def get_google_drive_mount_dir() -> Path | None:
    """Detect local Google Drive for Desktop mount directory (e.g., macOS CloudStorage)."""
    cloud_storage_pattern = str(Path.home() / "Library" / "CloudStorage" / "GoogleDrive-*")
    matches = glob.glob(cloud_storage_pattern)
    for match in matches:
        p = Path(match)
        # Check Korean '내 드라이브' or English 'My Drive'
        for drive_name in ["내 드라이브", "My Drive"]:
            drive_path = p / drive_name
            if drive_path.is_dir():
                return drive_path
    return None


def get_default_session_path() -> tuple[Path, str]:
    """
    Resolve default session file path and sync mode.
    Returns: (session_file_path, mode)
    mode can be 'env', 'gdrive_mount', or 'local'
    """
    # 1. Environment variable override
    env_path = os.getenv("NAVER_POINT_SESSION_PATH")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p, "env"

    # 2. Google Drive local mount
    gdrive_mount = get_google_drive_mount_dir()
    if gdrive_mount:
        target_dir = gdrive_mount / GOOGLE_DRIVE_SUBDIR
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / SESSION_FILENAME, "gdrive_mount"

    # 3. Fallback to OS standard local path
    DEFAULT_LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_LOCAL_DATA_DIR / SESSION_FILENAME, "local"
