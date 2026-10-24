import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

class StateManager:
    def __init__(self, data_dir: str):
        self.state_file = os.path.join(data_dir, "state.json")
        self._data: Dict[str, Any] = {"processed": {}, "last_synced": {}}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"processed": {}, "last_synced": {}}

    def _save(self) -> None:
        tmp_file = f"{self.state_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, self.state_file)

    def is_processed(self, message_id: str) -> bool:
        return message_id in self._data.get("processed", {})

    def mark_processed(self, message_id: str, handler_name: str, meta: Optional[Dict[str, Any]] = None) -> None:
        if "processed" not in self._data:
            self._data["processed"] = {}
        now_str = datetime.now().isoformat()
        self._data["processed"][message_id] = {
            "handler": handler_name,
            "processed_at": now_str,
            "meta": meta or {},
        }
        if "last_synced" not in self._data:
            self._data["last_synced"] = {}
        self._data["last_synced"][handler_name] = now_str
        self._save()

    def get_last_sync_time(self, handler_name: Optional[str] = None) -> Optional[str]:
        if handler_name:
            return self._data.get("last_synced", {}).get(handler_name)
        return max(self._data.get("last_synced", {}).values(), default=None)

    def get_all_processed(self) -> Dict[str, Any]:
        return self._data.get("processed", {})
