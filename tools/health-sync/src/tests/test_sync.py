import os
import tempfile
from datetime import datetime
from core.parser.csv_parser import parse_csv_activity
from core.builder.obsidian_builder import format_duration, format_pace, build_obsidian_markdown
from core.status import load_status, save_status, rebuild_status_from_vault

def test_format_helpers():
    assert format_duration(65) == "1분 5초"
    assert format_duration(3665) == "1시간 1분 5초"
    assert format_duration(0) == "0초"
    assert format_pace(360) == "6'00\""
    assert format_pace(355) == "5'55\""

def test_csv_parser():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("소스 앱,활동 유형,날짜,경과 시간,활성 시간,거리(km)\n")
        f.write("Samsung Health,RUNNING,2026.08.29 06:56:38,1566,1566,4.42\n")
        tmp_csv = f.name

    try:
        activity = parse_csv_activity(tmp_csv)
        assert activity["activity_type"] == "RUNNING"
        assert activity["distance_km"] == 4.42
        assert activity["duration_seconds"] == 1566
        assert activity["start_time"] == datetime(2026, 8, 29, 6, 56, 38)
    finally:
        os.remove(tmp_csv)

def test_build_obsidian_markdown():
    activity = {
        "key": "RUNNING-2026-08-29-0656",
        "activity_type": "RUNNING",
        "source_app": "Samsung Health",
        "start_time": datetime(2026, 8, 29, 6, 56, 38),
        "duration_seconds": 1566,
        "active_seconds": 1566,
        "distance_km": 4.42
    }
    details = {
        "calories": 327,
        "avg_heart_rate": 138,
        "max_heart_rate": 162,
        "avg_cadence": 87,
        "laps": []
    }
    md = build_obsidian_markdown(activity, details, gpx_link_name="RUNNING-2026-08-29-0656.gpx")
    assert "activity_type: RUNNING" in md
    assert "gpx_file: \"RUNNING-2026-08-29-0656.gpx\"" in md
    assert "# RUNNING - 2026-08-29 06:56" in md
    assert "327 kcal" in md
    assert "```leaflet" in md

def test_status_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        status_path = os.path.join(tmpdir, ".sync_status.json")
        save_status(status_path, datetime(2026, 8, 29, 12, 0), {"RUNNING-2026-08-29-0656"})
        
        status = load_status(status_path)
        assert status["last_sync_time"] == datetime(2026, 8, 29, 12, 0)
        assert "RUNNING-2026-08-29-0656" in status["processed_activities"]

        # Rebuild test
        vault_dir = os.path.join(tmpdir, "vault", "running")
        os.makedirs(vault_dir, exist_ok=True)
        with open(os.path.join(vault_dir, "RUNNING-2026-08-29-0656.md"), "w") as vf:
            vf.write("test")
        with open(os.path.join(vault_dir, "RUNNING-2026-08-30-0700 (1).md"), "w") as vf:
            vf.write("test")
            
        rebuilt = rebuild_status_from_vault(os.path.join(tmpdir, "vault"))
        assert "RUNNING-2026-08-29-0656" in rebuilt
        assert "RUNNING-2026-08-30-0700" in rebuilt
