import json
import logging
import os
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from core.config import load_config
from core.dispatcher import Dispatcher
from core.gog_client import GogClient
from core.state import StateManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mail-sync")

app = typer.Typer(
    name="mail-sync",
    help="2단 메일 자동화 파이프라인: Gmail 수신 감지 ➔ 복호화 ➔ Google Drive/Sheets & Obsidian 동기화",
    no_args_is_help=True,
)
console = Console()

# 글로벌 인프라 로드
config = load_config()
gog_client = GogClient(account=config.google_account)
state_manager = StateManager(config.data_dir)
dispatcher = Dispatcher(config, gog_client, state_manager)

# 서브모듈(핸들러) CLI 서브커맨드 동적 바인딩
for h_name, handler in dispatcher.handlers.items():
    sub_app = typer.Typer(name=h_name, help=f"{h_name} 서브모듈 전용 커맨드")
    handler.register_cli(sub_app)
    app.add_typer(sub_app, name=h_name)

@app.command("run")
def run_sync(
    handler: Optional[str] = typer.Argument(None, help="특정 핸들러만 실행 (생략 시 전체 실행)"),
    days: int = typer.Option(1, "--days", "-d", help="검색 대상 기간 (기본값: 최근 1일)"),
    month: Optional[str] = typer.Option(None, "--month", "-m", help="특정 연월 대상 (예: 2026-10)"),
    all_time: bool = typer.Option(False, "--all", "-a", help="기간 제한 없이 전체 메일 스캔"),
):
    """지정된 기간(기본: 최근 1일)의 메일을 스캔하여 파싱 및 동기화 수행"""
    is_tty = sys.stdout.isatty()
    target_handlers = [handler] if handler else None

    if is_tty:
        console.print(f"\n[bold cyan]🚀 mail-sync 실행 시작 (기본 검색 범위: 최근 {days}일)[/bold cyan]\n")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            main_task = progress.add_task("[cyan]동기화 파이프라인 실행 중...", total=None)

            def on_progress(msg: str, completed_ratio: Optional[float] = None):
                progress.update(main_task, description=f"[cyan]{msg}")
                if completed_ratio is not None:
                    progress.update(main_task, completed=int(completed_ratio * 100), total=100)

            results = dispatcher.run(
                target_handlers=target_handlers,
                days=days,
                month=month,
                all_time=all_time,
                progress_callback=on_progress,
            )
            progress.update(main_task, description="[bold green]동기화 완료!")
    else:
        # Non-TTY (crontab/서버 백그라운드)
        results = dispatcher.run(
            target_handlers=target_handlers,
            days=days,
            month=month,
            all_time=all_time,
            progress_callback=lambda msg, _: logger.info(msg),
        )

    # 결과 요약 브리핑
    console.print()
    summary_table = Table(title="📊 mail-sync 동기화 결과 요약", show_header=True, header_style="bold magenta")
    summary_table.add_column("핸들러", style="bold green")
    summary_table.add_column("상태", justify="center")
    summary_table.add_column("신규 처리", justify="right")
    summary_table.add_column("기처리 제외", justify="right")
    summary_table.add_column("요약 내용")

    total_processed = 0
    for r in results:
        status_style = "[green]성공[/green]" if r.success else "[red]실패[/red]"
        summary_table.add_row(
            r.handler_name,
            status_style,
            str(r.processed_count),
            str(r.skipped_count),
            r.summary,
        )
        total_processed += r.processed_count

    console.print(summary_table)
    console.print(f"[dim]총 처리된 신규 금융 데이터: {total_processed}건[/dim]\n")

@app.command("status")
def show_status():
    """등록된 핸들러 및 최근 동기화 통계 상태 확인"""
    console.print("\n[bold cyan]📋 mail-sync 상태 및 등록된 서브모듈[/bold cyan]\n")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("핸들러명", style="bold green")
    table.add_column("설명")
    table.add_column("최근 동기화 시각", style="yellow")
    table.add_column("누적 처리 메일 수", justify="right", style="cyan")

    history = state_manager.get_all_processed()

    for name, h in dispatcher.handlers.items():
        last_sync = state_manager.get_last_sync_time(name) or "기록 없음"
        count = sum(1 for v in history.values() if v.get("handler") == name)
        table.add_row(name, h.description, last_sync, str(count))

    console.print(table)
    console.print(f"\n[dim]데이터 저장소: {config.family_finance_dir}[/dim]\n")

@app.command("export")
def export_data(
    month: Optional[str] = typer.Option(None, "--month", "-m", help="특정 연월 필터 (예: 2026-10)"),
    as_json: bool = typer.Option(True, "--json", help="표준 JSON 포맷 출력 (외부 앱 연동용)"),
):
    """외부 애플리케이션 및 스크립트 연동을 위한 정규화된 금융 원장 데이터 내보내기"""
    history = state_manager.get_all_processed()
    items = []
    for entry in history.values():
        meta = entry.get("meta", {})
        if meta:
            if month and meta.get("billing_month") != month:
                continue
            items.append(meta)

    # 일자순 정렬
    items.sort(key=lambda x: x.get("due_date", ""))

    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        table = Table(title=f"금융 원장 데이터 ({month or '전체'})")
        table.add_column("ID")
        table.add_column("결제일")
        table.add_column("금융사")
        table.add_column("금액", justify="right")
        table.add_column("이율")
        for it in items:
            table.add_row(
                it.get("id", ""),
                it.get("due_date", ""),
                it.get("institution", ""),
                f"{it.get('total_amount', 0):,}원",
                it.get("interest_rate", ""),
            )
        console.print(table)

if __name__ == "__main__":
    app()
