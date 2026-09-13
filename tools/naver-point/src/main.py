"""naver-point CLI application entry point."""

import asyncio
import json
import logging
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import LOG_FILE
from core.session import NaverSessionManager
from core.collector import harvest_benefits, harvest_random_draws, fetch_point_balance
from core.sync import SessionSyncManager

# Setup application log to file only
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Silence root console loggers
for handler in logging.root.handlers[:]:
    if not isinstance(handler, logging.FileHandler):
        logging.root.removeHandler(handler)

app = typer.Typer(
    name="naver-point",
    help="네이버페이 혜택 포인트 자동 수집 및 랜덤 카드 뽑기 CLI 도구",
    add_completion=False,
)
sync_app = typer.Typer(name="sync", help="Google Drive 세션 동기화 관리", add_completion=False)
app.add_typer(sync_app, name="sync")

console = Console()
err_console = Console(stderr=True)


def print_json_result(data: dict):
    """Print clean single-line JSON to standard output."""
    print(json.dumps(data, ensure_ascii=False))


@app.command(name="login")
def login_cmd(
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """GUI 브라우저를 띄워 네이버 로그인 수행 및 세션 추출/동기화."""
    async def _login():
        session = NaverSessionManager(headless=False)
        try:
            if not json_mode:
                console.print(Panel.fit("🔑 [bold cyan]네이버 로그인[/bold cyan]을 시작합니다.\n브라우저 창에서 로그인을 완료해 주세요.", border_style="cyan"))

            def _status(msg: str):
                if not json_mode:
                    console.print(f"[yellow]{msg}[/yellow]")

            success = await session.login_interactive(status_callback=_status)
            if success:
                res = {"status": "Success", "message": "로그인 성공 및 세션 저장/동기화 완료", "session_path": str(session.session_path)}
                if json_mode:
                    print_json_result(res)
                else:
                    console.print("\n[bold green]✅ 네이버 로그인 완료 및 클라우드 동기화 완료![/bold green]")
                    console.print(f"세션 저장 위치: [cyan]{session.session_path}[/cyan]\n")
        except Exception as e:
            err_res = {"status": "Fail", "error_message": str(e)}
            if json_mode:
                print_json_result(err_res)
            else:
                err_console.print(f"[bold red]❌ 로그인 실패:[/bold red] {e}")
            sys.exit(1)
        finally:
            if session.context:
                await session.context.close()
            if session.playwright:
                await session.playwright.stop()

    asyncio.run(_login())


@app.command(name="run")
def run_cmd(
    headless: bool = typer.Option(True, "--headless/--no-headless", help="헤드리스 모드 실행 여부"),
    benefit_only: bool = typer.Option(False, "--benefit-only", "-b", help="혜택 페이지만 수집"),
    draw_only: bool = typer.Option(False, "--draw-only", "-d", help="랜덤 카드 뽑기만 수집"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="실제 클릭 없이 대상 요소만 스캔"),
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """포인트 자동 수집 및 랜덤 뽑기 실행."""
    async def _run():
        session = NaverSessionManager(headless=headless)
        async with session:
            # Check login session first
            logged_in = await session.is_logged_in()
            if not logged_in:
                err_res = {
                    "status": "SessionExpired",
                    "error_message": "네이버 로그인 세션이 없거나 만료되었습니다. 'naver-point login'을 실행해 주세요.",
                }
                if json_mode:
                    print_json_result(err_res)
                else:
                    err_console.print("[bold red]❌ 세션 만료:[/bold red] 로그인이 필요합니다. 터미널에서 [cyan]naver-point login[/cyan]을 실행해 주세요.")
                sys.exit(1)

            starting_balance = None
            ending_balance = None
            benefit_clicked = 0
            random_draws = 0

            # Initial Balance
            if not draw_only:
                try:
                    starting_balance = await fetch_point_balance(session)
                except Exception:
                    pass

            def _progress(msg: str):
                if not json_mode:
                    err_console.print(f"[dim]• {msg}[/dim]")

            # 1. Benefit Points
            if not draw_only:
                if not json_mode:
                    console.print("[cyan]🔍 혜택 포인트 수집 시작...[/cyan]")
                benefit_clicked, _ = await harvest_benefits(session, dry_run=dry_run, progress_callback=_progress)

            # 2. Random Draws
            if not benefit_only:
                if not json_mode:
                    console.print("[magenta]🎲 캠페인 랜덤 카드 뽑기 시작...[/magenta]")
                random_draws = await harvest_random_draws(session, dry_run=dry_run, progress_callback=_progress)

            # Final Balance
            try:
                ending_balance = await fetch_point_balance(session)
            except Exception:
                pass

            earned = None
            if starting_balance is not None and ending_balance is not None:
                earned = max(0, ending_balance - starting_balance)

            res = {
                "status": "Success",
                "benefit_clicked": benefit_clicked,
                "random_draws": random_draws,
                "starting_balance": starting_balance,
                "ending_balance": ending_balance,
                "earned_points": earned,
                "dry_run": dry_run,
                "session_synced": True,
            }

            if json_mode:
                print_json_result(res)
            else:
                console.print("\n[bold green]🎉 수집 작업이 성공적으로 완료되었습니다![/bold green]")
                table = Table(title="네이버 포인트 수집 결과", show_header=True, header_style="bold magenta")
                table.add_column("항목", style="cyan")
                table.add_column("수치 / 상태", justify="right", style="green")

                table.add_row("혜택 버튼 수집", f"{benefit_clicked} 건")
                table.add_row("랜덤 카드 뽑기", f"{random_draws} 회")
                if starting_balance is not None:
                    table.add_row("시작 포인트 잔액", f"{starting_balance:,} P")
                if ending_balance is not None:
                    table.add_row("최종 포인트 잔액", f"{ending_balance:,} P")
                if earned is not None:
                    table.add_row("실제 획득 포인트", f"+{earned:,} P", style="bold yellow")

                console.print(table)
                console.print()

    asyncio.run(_run())


@app.command(name="balance")
def balance_cmd(
    headless: bool = typer.Option(True, "--headless/--no-headless", help="헤드리스 실행"),
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """현재 네이버페이 포인트 잔액 조회."""
    async def _balance():
        session = NaverSessionManager(headless=headless)
        async with session:
            logged_in = await session.is_logged_in()
            if not logged_in:
                err_res = {"status": "SessionExpired", "error_message": "세션 만료. 'naver-point login'을 실행하세요."}
                if json_mode:
                    print_json_result(err_res)
                else:
                    err_console.print("[bold red]❌ 세션 만료:[/bold red] 로그인이 필요합니다. [cyan]naver-point login[/cyan]")
                sys.exit(1)

            bal = await fetch_point_balance(session)
            if bal is not None:
                res = {"status": "Success", "balance": bal}
                if json_mode:
                    print_json_result(res)
                else:
                    console.print(f"\n💰 현재 보유 네이버페이 포인트: [bold yellow]{bal:,} P[/bold yellow]\n")
            else:
                err_res = {"status": "Fail", "error_message": "포인트 잔액을 읽어오지 못했습니다."}
                if json_mode:
                    print_json_result(err_res)
                else:
                    err_console.print("[yellow]⚠️ 포인트 잔액 확인 실패[/yellow]")

    asyncio.run(_balance())


@app.command(name="status")
def status_cmd(
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """세션 유효성 및 클라우드 동기화 상태 점검."""
    async def _status():
        session = NaverSessionManager(headless=True)
        info = await session.get_session_info()
        res = {
            "status": "Success",
            "session_exists": info.get("exists", False),
            "has_cookie": info.get("has_session_cookie", False),
            "sync": info.get("sync", {}),
        }
        if json_mode:
            print_json_result(res)
        else:
            console.print("\n[bold cyan]📋 naver-point 세션 상태 점검[/bold cyan]")
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("항목", style="dim")
            table.add_column("값", style="white")

            sync_info = info.get("sync", {})
            table.add_row("세션 파일 경로", sync_info.get("session_path", "-"))
            table.add_row("동기화 모드", sync_info.get("mode", "-"))
            table.add_row("세션 파일 존재", "✅ 있음" if info.get("exists") else "❌ 없음")
            table.add_row("쿠키 유효성", "✅ NID_SES 존재" if info.get("has_session_cookie") else "⚠️ 쿠키 없음")
            gdrive = sync_info.get("google_drive_mount")
            table.add_row("Google Drive 마운트", gdrive if gdrive else "미감지 (gog 또는 로컬 모드)")
            table.add_row("gog CLI 사용 가능", "✅ 가능" if sync_info.get("gog_available") else "❌ 미설치")

            console.print(table)
            console.print()

    asyncio.run(_status())


@app.command(name="logout")
def logout_cmd(
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """로컬 및 클라우드 세션 파일 안전 삭제 및 초기화."""
    manager = SessionSyncManager()
    deleted = manager.delete()
    res = {"status": "Success", "session_deleted": deleted}
    if json_mode:
        print_json_result(res)
    else:
        if deleted:
            console.print("[bold green]✅ 세션 파일이 성공적으로 삭제되었습니다.[/bold green]")
        else:
            console.print("[dim]삭제할 세션 파일이 존재하지 않습니다.[/dim]")


@sync_app.command(name="push")
def sync_push_cmd(
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """로컬 세션을 Google Drive로 수동 업로드."""
    manager = SessionSyncManager()
    ok = manager.push()
    res = {"status": "Success" if ok else "Fail", "action": "push", "synced": ok}
    if json_mode:
        print_json_result(res)
    else:
        if ok:
            console.print("[bold green]✅ Google Drive 세션 업로드 성공![/bold green]")
        else:
            err_console.print("[bold red]❌ Google Drive 세션 업로드 실패 또는 세션 파일 없음[/bold red]")


@sync_app.command(name="pull")
def sync_pull_cmd(
    json_mode: bool = typer.Option(False, "--json", "-j", help="기계 판독용 JSON 출력"),
):
    """Google Drive에서 최신 세션을 수동 다운로드."""
    manager = SessionSyncManager()
    ok = manager.pull()
    res = {"status": "Success" if ok else "Fail", "action": "pull", "synced": ok}
    if json_mode:
        print_json_result(res)
    else:
        if ok:
            console.print("[bold green]✅ Google Drive 최신 세션 다운로드 완료![/bold green]")
        else:
            err_console.print("[bold red]❌ Google Drive 세션 다운로드 실패 또는 파일 없음[/bold red]")


if __name__ == "__main__":
    app()
