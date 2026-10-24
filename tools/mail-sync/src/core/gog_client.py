import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GogClient:
    def __init__(self, account: Optional[str] = None):
        self.account = account

    def _run(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        base_cmd = ["gog"]
        if self.account:
            base_cmd.extend(["-a", self.account])
        full_cmd = base_cmd + cmd
        return subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    def search_messages(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Gmail 검색 후 메시지 메타데이터 목록 반환"""
        cmd = ["gmail", "search", query, f"--max={max_results}", "--json"]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            logger.warning(f"gog gmail search failed: {proc.stderr}")
            return []
        
        try:
            data = json.loads(proc.stdout)
            # data can be list or dict with threads/messages
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("threads", []) or data.get("messages", []) or []
            return []
        except Exception as e:
            logger.error(f"Failed to parse search json: {e}")
            return []

    def get_message_raw(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Gmail 메시지 원본(Raw API 포맷) JSON 조회"""
        cmd = ["gmail", "raw", message_id]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            logger.error(f"gog gmail raw failed for {message_id}: {proc.stderr}")
            return None
        try:
            return json.loads(proc.stdout)
        except Exception as e:
            logger.error(f"Failed to parse raw message {message_id}: {e}")
            return None

    def download_attachment(self, message_id: str, attachment_id: str, out_path: str) -> bool:
        """첨부파일 다운로드"""
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        cmd = ["gmail", "attachment", message_id, attachment_id, f"--out={out_path}"]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            logger.error(f"gog gmail attachment download failed: {proc.stderr}")
            return False
        return os.path.exists(out_path)

    def find_file(self, query: str) -> Optional[Dict[str, Any]]:
        """Google Drive 파일/폴더 검색"""
        cmd = ["drive", "search", query, "--json", "--max=1"]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            return None
        try:
            res = json.loads(proc.stdout)
            if isinstance(res, list) and res:
                return res[0]
            if isinstance(res, dict) and res.get("files"):
                return res["files"][0]
        except Exception:
            pass
        return None

    def ensure_spreadsheet(self, title: str, parent_folder_id: str, default_sheet: str = "raw_ledger") -> Optional[str]:
        """구글 스프레드시트 존재 확인 및 없을 시 생성하여 ID 반환"""
        # 먼저 부모 폴더 내에 해당 이름의 스프레드시트가 있는지 확인
        q = f"name = '{title}' and '{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        existing = self.find_file(q)
        if existing and existing.get("id"):
            return existing["id"]

        # 전체 검색 fallback
        q_fallback = f"name = '{title}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        existing_fb = self.find_file(q_fallback)
        if existing_fb and existing_fb.get("id"):
            return existing_fb["id"]

        # 없으면 새로 생성
        cmd = ["sheets", "create", title, f"--parent={parent_folder_id}", f"--sheets={default_sheet}", "--json"]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            logger.error(f"Failed to create spreadsheet '{title}': {proc.stderr}")
            return None
        try:
            created = json.loads(proc.stdout)
            return created.get("spreadsheetId") or created.get("id")
        except Exception as e:
            logger.error(f"Failed to parse created spreadsheet output: {e}")
            return None

    def append_sheet_row(self, spreadsheet_id: str, sheet_name: str, row_values: List[Any]) -> bool:
        """구글 시트의 지정된 시트 탭에 행 추가"""
        val_strs = [str(v) if v is not None else "" for v in row_values]
        cmd = ["sheets", "append", spreadsheet_id, f"{sheet_name}!A:Z"] + val_strs
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            logger.warning(f"gog sheets append failed: {proc.stderr}")
            return False
        return True

    def get_sheet_values(self, spreadsheet_id: str, range_str: str) -> List[List[str]]:
        """스프레드시트 특정 범위 값 읽기"""
        cmd = ["sheets", "get", spreadsheet_id, range_str, "--plain"]
        proc = self._run(cmd, check=False)
        if proc.returncode != 0:
            return []
        lines = proc.stdout.strip().split("\n")
        return [l.split("\t") for l in lines if l]
