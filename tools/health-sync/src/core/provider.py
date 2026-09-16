import os
import re
import json
import shutil
import logging
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple

from core.config import HealthSyncConfig
from core.parser.csv_parser import find_matched_files, parse_csv_activity
from core.builder.obsidian_builder import generate_local_obsidian_note, build_obsidian_markdown
from core.status import rebuild_status_from_vault

logger = logging.getLogger("health-sync")

class HybridStorageProvider:
    """로컬 Google Drive 마운트 우선, 미발견 시 gog CLI로 자동 폴백하는 스토리지 공급자"""

    def __init__(self, config: HealthSyncConfig, cache_dir: str = ".cache"):
        self.config = config
        self.cache_dir = cache_dir
        self.raw_cache_dir = os.path.join(cache_dir, "raw_inputs")
        self.output_cache_dir = os.path.join(cache_dir, "output")
        self._target_subfolders_cache: Dict[str, str] = {}

    @property
    def is_local(self) -> bool:
        return self.config.is_local

    def fetch_existing_target_keys(self) -> Set[str]:
        """타깃 보관함 내에 이미 존재하는 노트의 키 목록 조회"""
        if self.is_local and self.config.target_dir:
            return rebuild_status_from_vault(self.config.target_dir)

        # gog CLI Fallback
        keys: Set[str] = set()
        if not self.config.gog_target_folder_id:
            return keys

        subfolders = self._gog_list_files(self.config.gog_target_folder_id)
        for item in subfolders:
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                folder_id = item.get("id")
                folder_files = self._gog_list_files(folder_id)
                for f_item in folder_files:
                    f_name = f_item.get("name", "")
                    if f_name.endswith(".md"):
                        stem = os.path.splitext(f_name)[0]
                        key = re.sub(r'\s*\(\d+\)$', '', stem)
                        keys.add(key)
        return keys

    def fetch_activities(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip_keys: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """소스 위치에서 미처리 운동 활동 세트(CSV + FIT + GPX) 조회"""
        if self.is_local and self.config.source_dir:
            return find_matched_files(
                input_dir=self.config.source_dir,
                start_date=start_date,
                end_date=end_date,
                skip_keys=skip_keys
            )

        # gog CLI Fallback: 원격 파일 조회 후 다운로드 매칭
        return self._fetch_activities_via_gog(start_date, end_date, skip_keys)

    def save_activity(self, activity: Dict[str, Any], details: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """마크다운 노트 및 GPX 생성/저장 (로컬 파일시스템 직접 작성 또는 gog 업로드)"""
        if self.is_local and self.config.target_dir:
            return generate_local_obsidian_note(activity, details, self.config.target_dir)

        # gog CLI Fallback
        act_type = activity["activity_type"]
        file_key = activity.get("key") or f"{act_type}-{activity['start_time'].strftime('%Y-%m-%d-%H%M')}"
        
        target_dir = os.path.join(self.output_cache_dir, act_type.lower())
        os.makedirs(target_dir, exist_ok=True)
        
        gpx_link_name = None
        local_gpx_path = None
        if activity.get("gpx_path") and os.path.exists(activity["gpx_path"]):
            gpx_link_name = f"{file_key}.gpx"
            local_gpx_path = os.path.join(target_dir, gpx_link_name)
            if not os.path.exists(local_gpx_path):
                shutil.copy(activity["gpx_path"], local_gpx_path)

        md_content = build_obsidian_markdown(activity, details, gpx_link_name)
        md_filename = f"{file_key}.md"
        local_md_path = os.path.join(target_dir, md_filename)
        with open(local_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Upload via gog
        subfolder_name = act_type.lower()
        self._gog_upload_file(local_md_path, subfolder_name)
        if local_gpx_path and os.path.exists(local_gpx_path):
            self._gog_upload_file(local_gpx_path, subfolder_name)

        return local_md_path, local_gpx_path

    def delete_source_files(self, activity: Dict[str, Any]) -> int:
        """처리 완료된 원본 소스 파일 삭제 (로컬 휴지통 이동 또는 gog rm)"""
        deleted_count = 0
        if self.is_local:
            for path_key in ("csv_path", "fit_path", "gpx_path"):
                path = activity.get(path_key)
                if path and os.path.exists(path):
                    try:
                        # macOS Finder 휴지통 이동 시도, 실패 시 os.remove 폴백
                        res = subprocess.run(
                            ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{path}"'],
                            capture_output=True,
                            check=False
                        )
                        if res.returncode != 0:
                            os.remove(path)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed deleting local file {path}: {e}")
            return deleted_count

        # gog CLI Fallback
        file_ids = activity.get("drive_file_ids", [])
        for f_id in file_ids:
            if self._gog_delete_file(f_id):
                deleted_count += 1
                
        # 캐시된 로컬 파일도 정리
        for path_key in ("csv_path", "fit_path", "gpx_path"):
            path = activity.get(path_key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
                    
        return deleted_count

    def cleanup(self) -> None:
        """임시 캐시 폴더 정리"""
        if os.path.exists(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
            except Exception as e:
                logger.warning(f"Failed removing cache dir {self.cache_dir}: {e}")

    # --- gog CLI Helpers ---
    def _gog_list_files(self, folder_id: str) -> List[Dict[str, Any]]:
        cmd = ["gog", "drive", "ls", "--json", "--max", "1000", "--parent", folder_id]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = json.loads(res.stdout)
            if isinstance(output, dict) and "files" in output:
                return output["files"]
            elif isinstance(output, list):
                return output
            return []
        except Exception as e:
            logger.error(f"gog drive ls error for folder '{folder_id}': {e}")
            return []

    def _gog_download_file(self, file_id: str, filename: str) -> Optional[str]:
        os.makedirs(self.raw_cache_dir, exist_ok=True)
        local_path = os.path.join(self.raw_cache_dir, filename)
        if os.path.exists(local_path):
            return local_path
        cmd = ["gog", "download", file_id, "--out", local_path]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return local_path
        except Exception as e:
            logger.error(f"gog download error for '{filename}' ({file_id}): {e}")
            return None

    def _gog_get_or_create_subfolder(self, subfolder_name: str) -> Optional[str]:
        target_id = self.config.gog_target_folder_id
        if not target_id:
            return None
        subfolder_key = subfolder_name.lower()
        if subfolder_key in self._target_subfolders_cache:
            return self._target_subfolders_cache[subfolder_key]

        existing = self._gog_list_files(target_id)
        for item in existing:
            if item.get("mimeType") == "application/vnd.google-apps.folder" and item.get("name", "").lower() == subfolder_key:
                fid = item.get("id")
                if fid:
                    self._target_subfolders_cache[subfolder_key] = fid
                    return fid

        cmd = ["gog", "drive", "mkdir", subfolder_name.lower(), "--parent", target_id, "--json"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            out = json.loads(res.stdout)
            fid = out.get("id") if isinstance(out, dict) else None
            if fid:
                self._target_subfolders_cache[subfolder_key] = fid
                return fid
        except Exception as e:
            logger.error(f"gog drive mkdir error for '{subfolder_name}': {e}")
        return None

    def _gog_upload_file(self, local_path: str, subfolder_name: str) -> bool:
        subfolder_id = self._gog_get_or_create_subfolder(subfolder_name)
        if not subfolder_id or not os.path.exists(local_path):
            return False
        filename = os.path.basename(local_path)
        cmd = ["gog", "drive", "upload", local_path, "--parent", subfolder_id, "-y"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except Exception as e:
            logger.error(f"gog drive upload error for '{filename}': {e}")
            return False

    def _gog_delete_file(self, file_id: str) -> bool:
        cmd = ["gog", "drive", "rm", file_id, "-y"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except Exception as e:
            logger.error(f"gog drive rm error for '{file_id}': {e}")
            return False

    def _fetch_activities_via_gog(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip_keys: Optional[Set[str]]
    ) -> List[Dict[str, Any]]:
        raw_files = self._gog_list_files(self.config.gog_source_folder_id)
        csv_files = [f for f in raw_files if f.get("name", "").endswith(".csv")]
        other_files = [f for f in raw_files if f.get("name", "").endswith((".fit", ".gpx"))]

        results = []
        for c in csv_files:
            c_name = c.get("name", "")
            c_id = c.get("id")
            if not c_id:
                continue

            local_csv = self._gog_download_file(c_id, c_name)
            if not local_csv:
                continue

            try:
                activity = parse_csv_activity(local_csv)
            except Exception:
                continue

            start_time = activity["start_time"]
            act_type = activity["activity_type"]
            file_key = f"{act_type}-{start_time.strftime('%Y-%m-%d-%H%M')}"

            if skip_keys and file_key in skip_keys:
                continue
            if start_date and start_time < start_date:
                continue
            if end_date and start_time > end_date:
                continue

            matched_fit = None
            matched_gpx = None
            drive_ids = [c_id]

            for o in other_files:
                o_name = o.get("name", "")
                o_id = o.get("id")
                if not o_name.startswith(act_type) or not o_id:
                    continue

                prefix = f"{act_type}-"
                parts = o_name[len(prefix):].rsplit(".", 1)[0]
                try:
                    file_time = datetime.strptime(parts, "%d.%m.%Y %H.%M")
                    if abs(start_time - file_time) <= timedelta(minutes=5):
                        local_down = self._gog_download_file(o_id, o_name)
                        drive_ids.append(o_id)
                        if o_name.endswith(".fit"):
                            matched_fit = local_down
                        elif o_name.endswith(".gpx"):
                            matched_gpx = local_down
                except ValueError:
                    continue

            activity["fit_path"] = matched_fit
            activity["gpx_path"] = matched_gpx
            activity["key"] = file_key
            activity["drive_file_ids"] = drive_ids
            results.append(activity)

        results.sort(key=lambda x: x["start_time"])
        return results
