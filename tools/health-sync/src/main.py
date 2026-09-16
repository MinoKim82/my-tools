import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Add src to sys.path for standalone execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config
from core.provider import HybridStorageProvider
from core.parser.fit_parser import parse_fit_details
from core.builder.obsidian_builder import format_duration
from core.status import load_status, save_status, rebuild_status_from_vault

app = typer.Typer(help="Health Sync to Obsidian pipeline")
console = Console()
err_console = Console(stderr=True)

STATUS_FILENAME = ".sync_status.json"

def get_status_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), STATUS_FILENAME)

@app.command()
def run(
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (YYYY-MM-DD)"),
    print_summary: bool = typer.Option(False, "-p", "--print", help="Print 1-line summary per synced note"),
    force_scan: bool = typer.Option(False, "-f", "--force-scan", help="Ignore status cache and re-scan target"),
    delete_source: bool = typer.Option(False, "--delete-source", help="Delete source files after processing"),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON to stdout")
):
    """건강 및 피트니스 활동 데이터를 Obsidian 볼트로 동기화합니다."""
    start_time_exec = datetime.now()
    log_stream = sys.stderr if json_output else sys.stdout
    logging.basicConfig(level=logging.WARNING if json_output else logging.INFO, stream=log_stream, format="%(message)s")

    try:
        config = load_config()
    except Exception as e:
        if json_output:
            print(json.dumps({"status": "error", "message": f"Failed loading config: {e}"}))
        else:
            err_console.print(f"[bold red]오류: 설정을 로드할 수 없습니다 - {e}[/bold red]")
        sys.exit(1)

    provider = HybridStorageProvider(config)
    status_path = get_status_path()
    status = load_status(status_path)
    last_sync = status.get("last_sync_time")
    processed_activities = status.get("processed_activities", set())

    if not json_output:
        mode_str = f"[bold green]로컬 마운트 직접 I/O[/bold green] ({config.source_dir})" if provider.is_local else "[bold yellow]gog CLI 원격 API[/bold yellow]"
        console.print(f"[bold blue]🏃 Health Sync 동기화 시작[/bold blue] (모드: {mode_str})")

    # Date parsing
    parsed_start = None
    parsed_end = None
    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            err_console.print(f"[red]유효하지 않은 시작 날짜 형식입니다: {start_date}[/red]")
            sys.exit(1)
    elif last_sync and not force_scan:
        parsed_start = last_sync - timedelta(days=2)

    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            err_console.print(f"[red]유효하지 않은 종료 날짜 형식입니다: {end_date}[/red]")
            sys.exit(1)

    # Rebuild existing target keys
    if force_scan or not last_sync:
        if not json_output:
            console.print("[dim]전체 재스캔 모드: 타깃 볼트의 기존 노트 키를 수집합니다...[/dim]")
        target_keys = provider.fetch_existing_target_keys()
        processed_activities.update(target_keys)

    # Fetch candidates
    activities = provider.fetch_activities(
        start_date=parsed_start,
        end_date=parsed_end,
        skip_keys=processed_activities if not force_scan else None
    )

    processed_count = 0
    skipped_count = 0
    deleted_source_count = 0
    synced_items = []

    if not activities:
        if json_output:
            print(json.dumps({
                "status": "success",
                "processed": 0,
                "skipped": len(processed_activities),
                "deleted_source": 0,
                "duration_seconds": round((datetime.now() - start_time_exec).total_seconds(), 2),
                "items": []
            }))
        else:
            console.print("[bold yellow]동기화할 새로운 운동 데이터가 없습니다.[/bold yellow]")
        save_status(status_path, start_time_exec, processed_activities)
        return

    # Process activities
    progress_ctx = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        disable=json_output
    )

    with progress_ctx as progress:
        task = progress.add_task("활동 노트 동기화 중...", total=len(activities))
        for act in activities:
            key = act["key"]
            if key in processed_activities and not force_scan:
                skipped_count += 1
                progress.advance(task)
                continue

            details = {}
            if act.get("fit_path"):
                try:
                    details = parse_fit_details(act["fit_path"], act["activity_type"])
                except Exception as e:
                    logging.warning(f"Failed parsing FIT {act['fit_path']}: {e}")

            try:
                md_path, gpx_path = provider.save_activity(act, details)
                processed_count += 1
                processed_activities.add(key)

                act_summary = {
                    "key": key,
                    "type": act["activity_type"],
                    "date": act["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "distance_km": act.get("distance_km", 0.0),
                    "duration": format_duration(act.get("duration_seconds", 0)),
                    "calories": details.get("calories")
                }
                synced_items.append(act_summary)

                if print_summary and not json_output:
                    console.print(f"  [green]✔[/green] [{act['activity_type']}] {act_summary['date']} - {act_summary['distance_km']:.2f}km, {act_summary['duration']}")

                if delete_source:
                    deleted = provider.delete_source_files(act)
                    deleted_source_count += deleted
            except Exception as e:
                err_console.print(f"[red]노트 생성 실패 ({key}): {e}[/red]")

            progress.advance(task)

    # Save state
    save_status(status_path, start_time_exec, processed_activities)
    provider.cleanup()

    duration_sec = round((datetime.now() - start_time_exec).total_seconds(), 2)

    if json_output:
        print(json.dumps({
            "status": "success",
            "processed": processed_count,
            "skipped": skipped_count,
            "deleted_source": deleted_source_count,
            "duration_seconds": duration_sec,
            "items": synced_items
        }, ensure_ascii=False))
    else:
        console.print(f"\n[bold green]동기화 완료![/bold green] (처리: {processed_count}건, 스킵: {skipped_count}건, 소스 정리: {deleted_source_count}건, 소요: {duration_sec}초)")

@app.command()
def status():
    """현재 동기화 상태 및 연결 정보를 확인합니다."""
    config = load_config()
    provider = HybridStorageProvider(config)
    status_data = load_status(get_status_path())

    table = Table(title="Health Sync 상태 대시보드")
    table.add_column("항목", style="cyan", no_wrap=True)
    table.add_column("값", style="white")

    table.add_row("작동 모드", "로컬 마운트 직접 I/O" if provider.is_local else "gog CLI 원격 API")
    table.add_row("소스 디렉토리", config.source_dir or f"gog folder ID: {config.gog_source_folder_id}")
    table.add_row("타깃 보관함", config.target_dir or f"gog folder ID: {config.gog_target_folder_id}")
    table.add_row("마지막 동기화", str(status_data.get("last_sync_time") or "기록 없음"))
    table.add_row("누적 처리 활동 수", f"{len(status_data.get('processed_activities', []))}개")

    console.print(table)

if __name__ == "__main__":
    app()
