from datetime import timedelta
from typing import Optional, Dict, Any, List
from fitparse import FitFile

def calculate_swimming_virtual_laps(fitfile, total_distance, total_timer_time, start_time):
    if not total_distance or not total_timer_time or total_distance < 100.0 or not start_time:
        return None
        
    records = []
    for r in fitfile.get_messages('record'):
        t = r.get_value('timestamp')
        hr = r.get_value('heart_rate')
        if t is not None:
            records.append({'timestamp': t, 'heart_rate': hr})
            
    records.sort(key=lambda x: x['timestamp'])
    
    num_laps = int(total_distance // 100)
    remainder = total_distance % 100
    
    laps = []
    lap_duration_sec = total_timer_time / (total_distance / 100.0)
    
    current_time = start_time
    for i in range(num_laps):
        lap_idx = i + 1
        next_time = current_time + timedelta(seconds=lap_duration_sec)
        
        hr_list = [r['heart_rate'] for r in records if r['heart_rate'] is not None and current_time <= r['timestamp'] < next_time]
        avg_hr = int(sum(hr_list)/len(hr_list)) if hr_list else None
        
        laps.append({
            "lap_num": lap_idx,
            "distance_km": 100.0,
            "duration_sec": lap_duration_sec,
            "avg_heart_rate": avg_hr
        })
        current_time = next_time
        
    if remainder > 0.0:
        remainder_duration = total_timer_time * (remainder / total_distance)
        next_time = current_time + timedelta(seconds=remainder_duration)
        hr_list = [r['heart_rate'] for r in records if r['heart_rate'] is not None and current_time <= r['timestamp'] < next_time]
        avg_hr = int(sum(hr_list)/len(hr_list)) if hr_list else None
        
        laps.append({
            "lap_num": num_laps + 1,
            "distance_km": remainder,
            "duration_sec": remainder_duration,
            "avg_heart_rate": avg_hr
        })
        
    return laps

def calculate_virtual_laps(fitfile, activity_type):
    if activity_type != "RUNNING":
        return None
        
    records = []
    last_dist = 0.0
    for r in fitfile.get_messages('record'):
        t = r.get_value('timestamp')
        d = r.get_value('distance')
        hr = r.get_value('heart_rate')
        cad = r.get_value('cadence')
        
        if t is None:
            continue
        if d is not None:
            last_dist = d
            
        records.append({
            'timestamp': t,
            'distance': last_dist,
            'heart_rate': hr,
            'cadence': cad
        })
        
    if not records:
        return None
        
    records.sort(key=lambda x: x['timestamp'])
    
    laps = []
    lap_idx = 1
    
    lap_start_rec = records[0]
    next_target = 1000.0
    
    hr_list = []
    cad_list = []
    
    for rec in records:
        if rec['heart_rate'] is not None:
            hr_list.append(rec['heart_rate'])
        if rec['cadence'] is not None:
            cad_list.append(rec['cadence'])
            
        if rec['distance'] >= next_target:
            duration_sec = (rec['timestamp'] - lap_start_rec['timestamp']).total_seconds()
            lap_dist_m = rec['distance'] - lap_start_rec['distance']
            
            if lap_dist_m > 0 and duration_sec > 0:
                laps.append({
                    "lap_num": lap_idx,
                    "distance_km": lap_dist_m / 1000.0,
                    "duration_sec": duration_sec,
                    "avg_heart_rate": int(sum(hr_list)/len(hr_list)) if hr_list else None,
                    "avg_cadence": int(sum(cad_list)/len(cad_list)) if cad_list else None
                })
                lap_idx += 1
                
            lap_start_rec = rec
            next_target += 1000.0
            hr_list = []
            cad_list = []
            
    last_rec = records[-1]
    remainder_dist_m = last_rec['distance'] - lap_start_rec['distance']
    if remainder_dist_m > 50.0:
        duration_sec = (last_rec['timestamp'] - lap_start_rec['timestamp']).total_seconds()
        laps.append({
            "lap_num": lap_idx,
            "distance_km": remainder_dist_m / 1000.0,
            "duration_sec": duration_sec,
            "avg_heart_rate": int(sum(hr_list)/len(hr_list)) if hr_list else None,
            "avg_cadence": int(sum(cad_list)/len(cad_list)) if cad_list else None
        })
        
    return laps

def parse_fit_details(fit_path: Optional[str], activity_type: str) -> Dict[str, Any]:
    if not fit_path:
        return {}
        
    try:
        fitfile = FitFile(fit_path)
    except Exception:
        return {}

    details: Dict[str, Any] = {
        "calories": None,
        "avg_heart_rate": None,
        "max_heart_rate": None,
        "avg_cadence": None,
        "max_cadence": None,
        "laps": [],
        "strokes_total": None,
        "avg_swolf": None
    }
    
    total_dist_session = None
    total_time_session = None
    start_time_session = None
    
    for session in fitfile.get_messages('session'):
        details["calories"] = session.get_value("total_calories")
        details["avg_heart_rate"] = session.get_value("avg_heart_rate")
        details["max_heart_rate"] = session.get_value("max_heart_rate")
        
        total_dist_session = session.get_value("total_distance")
        total_time_session = session.get_value("total_timer_time") or session.get_value("total_moving_time")
        start_time_session = session.get_value("start_time")
        
        if activity_type == "RUNNING":
            details["avg_cadence"] = session.get_value("avg_cadence")
            details["max_cadence"] = session.get_value("max_cadence")
        elif activity_type == "SWIMMING":
            details["strokes_total"] = session.get_value("total_strokes")
            details["avg_swolf"] = session.get_value("avg_swolf")
            
    lap_messages = list(fitfile.get_messages('lap'))
    
    if activity_type == "RUNNING" and len(lap_messages) <= 1:
        virtual_laps = calculate_virtual_laps(fitfile, activity_type)
        if virtual_laps:
            details["laps"] = virtual_laps
            return details
            
    elif activity_type == "SWIMMING" and len(lap_messages) <= 1:
        virtual_laps = calculate_swimming_virtual_laps(
            fitfile, 
            total_dist_session, 
            total_time_session, 
            start_time_session
        )
        if virtual_laps:
            details["laps"] = virtual_laps
            return details
            
    lap_idx = 1
    for lap in lap_messages:
        distance_m = lap.get_value("total_distance") or 0.0
        elapsed_sec = lap.get_value("total_elapsed_time") or 0.0
        avg_hr = lap.get_value("avg_heart_rate")
        
        lap_data: Dict[str, Any] = {
            "lap_num": lap_idx,
            "distance_km": distance_m / 1000.0 if activity_type == "RUNNING" else distance_m,
            "duration_sec": elapsed_sec,
            "avg_heart_rate": avg_hr
        }
        
        if activity_type == "RUNNING":
            lap_data["avg_cadence"] = lap.get_value("avg_cadence")
        elif activity_type == "SWIMMING":
            lap_data["strokes"] = lap.get_value("total_strokes")
            stroke_val = lap.get_value("swim_stroke")
            lap_data["stroke_type"] = format_stroke_type(stroke_val)
            
        details["laps"].append(lap_data)
        lap_idx += 1
        
    return details

def format_stroke_type(stroke_val: Any) -> str:
    if stroke_val is None:
        return "-"
    stroke_map = {
        0: "자유형",
        1: "배영",
        2: "평영",
        3: "접영",
        4: "드릴",
        5: "혼영"
    }
    if isinstance(stroke_val, int):
        return stroke_map.get(stroke_val, f"기타 ({stroke_val})")
    
    stroke_str = str(stroke_val).lower()
    stroke_str_map = {
        "freestyle": "자유형",
        "backstroke": "배영",
        "breaststroke": "평영",
        "butterfly": "접영",
        "drill": "드릴",
        "mixed": "혼영"
    }
    return stroke_str_map.get(stroke_str, str(stroke_val))
