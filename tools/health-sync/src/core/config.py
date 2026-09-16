import os
import glob
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

@dataclass
class HealthSyncConfig:
    source_dir: Optional[str]
    target_dir: Optional[str]
    gog_source_folder_id: str
    gog_target_folder_id: str
    is_local: bool

def find_default_cloud_storage_paths() -> tuple[Optional[str], Optional[str]]:
    """macOS Google Drive CloudStorage 마운트 경로 자동 탐색"""
    home = os.path.expanduser("~")
    pattern = os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "내 드라이브")
    matches = glob.glob(pattern)
    
    # 영문 'My Drive'도 탐색
    if not matches:
        pattern_en = os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "My Drive")
        matches = glob.glob(pattern_en)
        
    for drive_path in matches:
        source_cand = os.path.join(drive_path, "Health Sync 활동")
        target_cand = os.path.join(drive_path, "obsidian", "workout")
        if os.path.exists(source_cand) and os.path.exists(target_cand):
            return source_cand, target_cand
        if os.path.exists(source_cand):
            return source_cand, target_cand

    return None, None

def load_config() -> HealthSyncConfig:
    """설정 로드 (.env 우선 -> 로컬 마운트 자동 감지 -> gog 폴백)"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)

    env_source = os.environ.get("LOCAL_SOURCE_DIR")
    env_target = os.environ.get("LOCAL_TARGET_DIR")
    
    gog_source = os.environ.get("GOG_SOURCE_FOLDER_ID", "1cLQ-wLPwGXky2KrvMctZUvUfzUGAnH-f")
    gog_target = os.environ.get("GOG_TARGET_FOLDER_ID", "11r4bcpUZ2IFEqDS7jl3JT1ZiC4e1oqNH")

    auto_source, auto_target = find_default_cloud_storage_paths()
    source_dir = env_source or auto_source
    target_dir = env_target or auto_target
    
    is_local = bool(source_dir and os.path.exists(source_dir) and target_dir)

    return HealthSyncConfig(
        source_dir=source_dir,
        target_dir=target_dir,
        gog_source_folder_id=gog_source,
        gog_target_folder_id=gog_target,
        is_local=is_local
    )
