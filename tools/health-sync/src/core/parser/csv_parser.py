import os
import re
import glob
import csv
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set

def parse_csv_activity(csv_path: str) -> Dict[str, Any]:
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        try:
            row = next(reader)
        except StopIteration:
            raise ValueError(f"Empty CSV file: {csv_path}")
            
        source_app = row.get("소스 앱") or "Unknown"
        activity_type = row.get("활동 유형") or "UNKNOWN"
        start_time_str = row.get("날짜") or ""
        
        try:
            duration_seconds = int(float(row.get("경과 시간", 0)))
        except ValueError:
            duration_seconds = 0
            
        try:
            active_seconds = int(float(row.get("활성 시간", 0)))
        except ValueError:
            active_seconds = 0
            
        try:
            distance_km = float(row.get("거리(km)", 0.0))
        except ValueError:
            distance_km = 0.0
            
        try:
            start_time = datetime.strptime(start_time_str, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValueError(f"Unknown datetime format: {start_time_str}")
        
        return {
            "source_app": source_app,
            "activity_type": activity_type,
            "start_time": start_time,
            "duration_seconds": duration_seconds,
            "active_seconds": active_seconds,
            "distance_km": distance_km,
            "csv_path": csv_path
        }

def find_matched_files(
    input_dir: str, 
    last_sync_time: Optional[datetime] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip_keys: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    if not os.path.exists(input_dir):
        return []
        
    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
    results = []
    
    # Pre-read all fit and gpx files in directory for high-speed matching
    all_files = os.listdir(input_dir)
    fit_gpx_files = [f for f in all_files if f.endswith(".fit") or f.endswith(".gpx")]
    
    filter_time = None
    if start_date:
        filter_time = start_date
    elif last_sync_time:
        filter_time = last_sync_time - timedelta(days=2)
        
    for csv_path in csv_files:
        base_name = os.path.basename(csv_path)
        # Fast pre-filtering by filename date to avoid opening thousands of CSVs
        if filter_time:
            m_date = re.search(r'(\d{4})[\.-](\d{2})[\.-](\d{2})', base_name)
            if m_date:
                try:
                    file_d = datetime(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)))
                    if file_d.date() < filter_time.date():
                        continue
                except ValueError:
                    pass
        if end_date:
            m_date = re.search(r'(\d{4})[\.-](\d{2})[\.-](\d{2})', base_name)
            if m_date:
                try:
                    file_d = datetime(int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3)))
                    if file_d.date() > end_date.date():
                        continue
                except ValueError:
                    pass

        try:
            activity = parse_csv_activity(csv_path)
        except Exception:
            continue
            
        start_time = activity["start_time"]
        activity_type = activity["activity_type"]
        file_key = f"{activity_type}-{start_time.strftime('%Y-%m-%d-%H%M')}"
        
        if skip_keys and file_key in skip_keys:
            continue
            
        if filter_time and start_time < filter_time:
            continue
        if end_date and start_time > end_date:
            continue
            
        matched_fit = None
        matched_gpx = None
        
        for f_name in fit_gpx_files:
            if not f_name.startswith(activity_type):
                continue
                
            prefix = f"{activity_type}-"
            parts = f_name[len(prefix):].rsplit(".", 1)[0]
            
            try:
                file_time = datetime.strptime(parts, "%d.%m.%Y %H.%M")
                if abs(start_time - file_time) <= timedelta(minutes=5):
                    full_path = os.path.join(input_dir, f_name)
                    if f_name.endswith(".fit"):
                        matched_fit = full_path
                    elif f_name.endswith(".gpx"):
                        matched_gpx = full_path
            except ValueError:
                continue
                
        activity["fit_path"] = matched_fit
        activity["gpx_path"] = matched_gpx
        activity["key"] = file_key
        results.append(activity)
        
    results.sort(key=lambda x: x["start_time"])
    return results
