import os
import shutil
from typing import Dict, Any, Tuple

def format_duration(seconds: Any) -> str:
    if seconds is None or seconds <= 0:
        return "0초"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    hours = minutes // 60
    minutes = minutes % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}시간")
    if minutes > 0:
        parts.append(f"{minutes}분")
    if secs > 0 or not parts:
        parts.append(f"{secs}초")
        
    return " ".join(parts)

def format_pace(seconds_per_km: Any) -> str:
    if not seconds_per_km or seconds_per_km <= 0:
        return "-"
    minutes = int(seconds_per_km) // 60
    secs = int(seconds_per_km) % 60
    return f"{minutes}'{secs:02d}\""

def build_obsidian_markdown(activity: Dict[str, Any], details: Dict[str, Any], gpx_link_name: str | None = None) -> str:
    start_time = activity["start_time"]
    act_type = activity["activity_type"]
    file_key = activity.get("key") or f"{act_type}-{start_time.strftime('%Y-%m-%d-%H%M')}"
    
    # 1. Frontmatter
    frontmatter = [
        "---",
        f"activity_type: {act_type}",
        f"source_app: {activity.get('source_app', 'Unknown')}",
        f"start_time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"duration_seconds: {activity.get('duration_seconds', 0)}",
        f"active_seconds: {activity.get('active_seconds', 0)}",
        f"distance_km: {activity.get('distance_km', 0.0):.2f}",
    ]
    
    if details.get("calories"):
        frontmatter.append(f"calories_kcal: {details['calories']}")
    if details.get("avg_heart_rate"):
        frontmatter.append(f"avg_heart_rate: {details['avg_heart_rate']}")
    if details.get("max_heart_rate"):
        frontmatter.append(f"max_heart_rate: {details['max_heart_rate']}")
    if details.get("avg_cadence"):
        frontmatter.append(f"avg_cadence: {details['avg_cadence']}")
    if gpx_link_name:
        frontmatter.append(f"gpx_file: \"{gpx_link_name}\"")
        
    frontmatter.append("tags:")
    frontmatter.append("  - health/activity")
    frontmatter.append(f"  - health/{act_type.lower()}")
    frontmatter.append("---")
    
    # 2. Body Summary
    body = [
        f"# {act_type} - {start_time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 📊 운동 요약",
        "",
        "| 항목 | 상세 정보 |",
        "| :--- | :--- |",
        f"| **활동 유형** | {act_type} |",
        f"| **날짜 및 시간** | {start_time.strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| **경과 시간** | {format_duration(activity.get('duration_seconds', 0))} |",
        f"| **활성 시간** | {format_duration(activity.get('active_seconds', 0))} |",
        f"| **이동 거리** | {activity.get('distance_km', 0.0):.2f} km |",
    ]
    
    if details.get("calories"):
        body.append(f"| **소모 칼로리** | {details['calories']} kcal |")
        
    body.append("")
    body.append("## 💓 신체 및 페이스 정보")
    body.append("")
    body.append("| 항목 | 수치 |")
    body.append("| :--- | :--- |")
    
    if details.get("avg_heart_rate"):
        body.append(f"| **평균 심박수** | {details['avg_heart_rate']} bpm |")
    if details.get("max_heart_rate"):
        body.append(f"| **최대 심박수** | {details['max_heart_rate']} bpm |")
        
    if act_type == "RUNNING":
        dist = activity.get("distance_km", 0.0)
        act_sec = activity.get("active_seconds", 0)
        if dist > 0:
            pace_sec = act_sec / dist
            body.append(f"| **평균 페이스** | {format_pace(pace_sec)} / km |")
        if details.get("avg_cadence"):
            body.append(f"| **평균 케이던스** | {details['avg_cadence']} spm |")
        if details.get("max_cadence"):
            body.append(f"| **최대 케이던스** | {details['max_cadence']} spm |")
            
    elif act_type == "SWIMMING":
        dist = activity.get("distance_km", 0.0)
        dist_m = dist if dist > 5.0 else dist * 1000.0
        act_sec = activity.get("active_seconds", 0)
        if dist_m > 0:
            pace_100m = (act_sec / dist_m) * 100.0
            body.append(f"| **평균 페이스** | {format_pace(pace_100m)} / 100m |")
        if details.get("strokes_total"):
            body.append(f"| **총 스트로크** | {details['strokes_total']} strokes |")
        if details.get("avg_swolf"):
            body.append(f"| **평균 SWOLF** | {details['avg_swolf']} |")
            
    # Laps
    if details.get("laps"):
        body.append("")
        body.append("## ⏱️ 구간별 상세 기록 (Laps)")
        body.append("")
        if act_type == "RUNNING":
            body.append("| 구간 | 거리 | 시간 | 평균 페이스 | 평균 심박수 | 평균 케이던스 |")
            body.append("| :---: | :---: | :---: | :---: | :---: | :---: |")
            for lap in details["laps"]:
                lap_dist = lap["distance_km"]
                lap_time = format_duration(lap["duration_sec"])
                lap_pace = format_pace(lap["duration_sec"] / lap_dist) if lap_dist > 0 else "-"
                lap_hr = f"{lap['avg_heart_rate']} bpm" if lap.get("avg_heart_rate") else "-"
                lap_cad = f"{lap['avg_cadence']} spm" if lap.get("avg_cadence") else "-"
                body.append(f"| {lap['lap_num']} | {lap_dist:.2f} km | {lap_time} | {lap_pace} | {lap_hr} | {lap_cad} |")
        elif act_type == "SWIMMING":
            body.append("| 구간 | 거리 | 시간 | 페이스 (/100m) | 평균 심박수 |")
            body.append("| :---: | :---: | :---: | :---: | :---: |")
            for lap in details["laps"]:
                lap_dist = lap["distance_km"]
                lap_time = format_duration(lap["duration_sec"])
                lap_pace = format_pace((lap["duration_sec"] / lap_dist) * 100.0) if lap_dist > 0 else "-"
                lap_hr = f"{lap['avg_heart_rate']} bpm" if lap.get("avg_heart_rate") else "-"
                body.append(f"| {lap['lap_num']} | {lap_dist:.0f} m | {lap_time} | {lap_pace} | {lap_hr} |")
                
    if gpx_link_name:
        body.append("")
        body.append("## 🗺️ 이동 경로 (GPS)")
        body.append("")
        body.append("```leaflet")
        body.append(f"id: {file_key.lower()}")
        body.append(f"gpx: [[{gpx_link_name}]]")
        body.append("```")
        
    return "\n".join(frontmatter) + "\n\n" + "\n".join(body) + "\n"

def generate_local_obsidian_note(activity: Dict[str, Any], details: Dict[str, Any], output_dir: str) -> Tuple[str, str | None]:
    """로컬 파일시스템 모드: 노트와 GPX 파일을 대상 폴더에 직접 생성"""
    start_time = activity["start_time"]
    act_type = activity["activity_type"]
    target_dir = os.path.join(output_dir, act_type.lower())
    os.makedirs(target_dir, exist_ok=True)
    
    file_key = activity.get("key") or f"{act_type}-{start_time.strftime('%Y-%m-%d-%H%M')}"
    md_path = os.path.join(target_dir, f"{file_key}.md")
    
    gpx_dest_path = None
    gpx_link_name = None
    if activity.get("gpx_path") and os.path.exists(activity["gpx_path"]):
        gpx_filename = f"{file_key}.gpx"
        gpx_dest_path = os.path.join(target_dir, gpx_filename)
        if not os.path.exists(gpx_dest_path):
            shutil.copy(activity["gpx_path"], gpx_dest_path)
        gpx_link_name = gpx_filename

    md_content = build_obsidian_markdown(activity, details, gpx_link_name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    return md_path, gpx_dest_path
