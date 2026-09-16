import os
import json
import re
from datetime import datetime
from typing import Set, Dict, Any, Optional

def load_status(status_path: str) -> Dict[str, Any]:
    default_status: Dict[str, Any] = {"last_sync_time": None, "processed_activities": set()}
    if not os.path.exists(status_path):
        return default_status
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_sync_str = data.get("last_sync_time")
            last_sync_time = datetime.fromisoformat(last_sync_str) if last_sync_str else None
            processed = set(data.get("processed_activities", []))
            return {
                "last_sync_time": last_sync_time,
                "processed_activities": processed
            }
    except Exception:
        return default_status

def save_status(status_path: str, last_sync_time: Optional[datetime], processed_activities: Set[str]) -> None:
    data = {
        "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
        "processed_activities": sorted(list(processed_activities))
    }
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def rebuild_status_from_vault(vault_dir: str) -> Set[str]:
    keys: Set[str] = set()
    if not os.path.exists(vault_dir):
        return keys
    for root, _, files in os.walk(vault_dir):
        for file in files:
            if file.endswith(".md"):
                key = os.path.splitext(file)[0]
                normalized_key = re.sub(r'\s*\(\d+\)$', '', key)
                keys.add(normalized_key)
    return keys
