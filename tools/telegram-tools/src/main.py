import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from telethon import TelegramClient, errors
from telethon.tl.types import Channel, Chat, MessageMediaDocument, MessageMediaPhoto, User

app = typer.Typer(help="Telegram chat export (JSON/MD) and message sender CLI", no_args_is_help=True)
console = Console()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSION_FILE = DATA_DIR / "telegram_user.session"

load_dotenv(BASE_DIR / ".env")


def get_credentials() -> tuple[int, str, Optional[str]]:
    api_id_str = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not api_id_str or not api_hash:
        console.print("[bold red]오류:[/bold red] TELEGRAM_API_ID 또는 TELEGRAM_API_HASH가 설정되지 않았습니다.")
        console.print(f"설정 파일: {BASE_DIR / '.env'} 에 환경변수를 입력해주세요.")
        raise typer.Exit(code=1)

    try:
        api_id = int(api_id_str)
    except ValueError:
        console.print("[bold red]오류:[/bold red] TELEGRAM_API_ID는 숫자여야 합니다.")
        raise typer.Exit(code=1)

    return api_id, api_hash, phone


def get_client() -> TelegramClient:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    api_id, api_hash, _ = get_credentials()
    return TelegramClient(str(SESSION_FILE.with_suffix("")), api_id, api_hash)


def parse_relative_or_absolute_time(val: str, tz: timezone) -> datetime:
    val = val.strip().lower()
    now = datetime.now(tz)

    if val == "now":
        return now
    if val == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if val == "yesterday":
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Relative match: 10m, 2h, 3d, 1w
    rel_match = re.match(r"^(\d+)\s*([m|h|d|w])$", val)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit == "m":
            return now - timedelta(minutes=qty)
        if unit == "h":
            return now - timedelta(hours=qty)
        if unit == "d":
            return now - timedelta(days=qty)
        if unit == "w":
            return now - timedelta(weeks=qty)

    # Absolute formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ):
        try:
            parsed = datetime.strptime(val, fmt)
            return parsed.replace(tzinfo=tz)
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(val)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed
    except ValueError:
        raise ValueError(
            f"인식할 수 없는 시간 포맷: '{val}'. (예: '2h', '3d', 'yesterday', '2026-09-20 15:00')"
        )


def chunk_text(text: str, max_len: int = 4000) -> list[str]:
    # ponytail: naive newline split, upgrade to AST/markdown-aware split if code blocks break
    if len(text) <= max_len:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        para_len = len(paragraph) + 2
        if current_len + para_len > max_len:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            if len(paragraph) > max_len:
                # Fallback to line split
                for line in paragraph.split("\n"):
                    if current_len + len(line) + 1 > max_len and current_chunk:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = []
                        current_len = 0
                    current_chunk.append(line)
                    current_len += len(line) + 1
            else:
                current_chunk.append(paragraph)
                current_len = para_len
        else:
            current_chunk.append(paragraph)
            current_len += para_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


async def resolve_target_entity(client: TelegramClient, chat_target: str) -> Any:
    # Try integer ID (user ID, group -ID, channel -100ID)
    try:
        chat_id = int(chat_target)
        try:
            return await client.get_entity(chat_id)
        except Exception:
            # If positive integer fails for channel/supergroup, try -100 prefix
            if chat_id > 0:
                try:
                    return await client.get_entity(int(f"-100{chat_id}"))
                except Exception:
                    pass
    except ValueError:
        pass

    # Try username or direct string lookup
    try:
        return await client.get_entity(chat_target)
    except Exception:
        pass

    # Match dialog title substring
    async for dialog in client.iter_dialogs(limit=200):
        if chat_target.lower() in dialog.name.lower():
            return dialog.entity

    raise ValueError(f"대화방 '{chat_target}'을(를) 찾을 수 없습니다. (ID, username 또는 대화방명을 확인해주세요)")


def get_entity_info(entity: Any) -> tuple[int, str, str, Optional[str]]:
    entity_id = getattr(entity, "id", 0)
    username = getattr(entity, "username", None)
    if isinstance(entity, User):
        name = f"{entity.first_name or ''} {entity.last_name or ''}".strip() or entity.first_name or "Unknown"
        chat_type = "user"
    elif isinstance(entity, Channel):
        name = entity.title
        chat_type = "channel" if entity.broadcast else "supergroup"
    elif isinstance(entity, Chat):
        name = entity.title
        chat_type = "group"
    else:
        name = getattr(entity, "title", str(entity_id))
        chat_type = "unknown"
    return entity_id, name, chat_type, username


@app.command("login")
def login() -> None:
    """텔레그램 대화형 로그인 및 세션 생성"""
    _, _, default_phone = get_credentials()

    async def _login():
        client = get_client()
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            console.print(f"[bold green]이미 로그인되어 있습니다:[/bold green] {me.first_name} (@{me.username})")
            await client.disconnect()
            return

        phone = default_phone or typer.prompt("전화번호를 입력하세요 (국제전화 형식, 예: +821012345678)")
        await client.start(phone=phone)
        me = await client.get_me()
        console.print(f"[bold green]로그인 성공![/bold green] 세션이 저장되었습니다: {me.first_name} (ID: {me.id})")
        await client.disconnect()

    asyncio.run(_login())


@app.command("status")
def status() -> None:
    """현재 로그인 세션 상태 및 내 계정 정보 확인"""
    async def _status():
        client = get_client()
        await client.connect()
        if not await client.is_user_authorized():
            console.print("[bold yellow]상태:[/bold yellow] 로그인되어 있지 않습니다. `telegram-tools login`을 실행하세요.")
            await client.disconnect()
            raise typer.Exit(1)

        me = await client.get_me()
        console.print("[bold green]✓ 텔레그램 세션 정상 연결됨[/bold green]")
        table = Table(show_header=False, box=None)
        table.add_row("사용자 ID", str(me.id))
        table.add_row("이름", f"{me.first_name or ''} {me.last_name or ''}".strip())
        table.add_row("Username", f"@{me.username}" if me.username else "(없음)")
        table.add_row("전화번호", f"+{me.phone}" if me.phone else "(비공개)")
        table.add_row("세션 경로", str(SESSION_FILE))
        console.print(table)
        await client.disconnect()

    asyncio.run(_status())


@app.command("chats")
def chats(
    search: Optional[str] = typer.Option(None, "--search", "-s", help="대화방 이름 검색어"),
    limit: int = typer.Option(20, "--limit", "-l", help="조회할 대화방 개수"),
) -> None:
    """대화방 목록 조회 및 ID 검색"""
    async def _chats():
        client = get_client()
        await client.connect()
        if not await client.is_user_authorized():
            console.print("[bold red]로그인이 필요합니다.[/bold red] 먼저 `telegram-tools login`을 실행하세요.")
            await client.disconnect()
            raise typer.Exit(1)

        table = Table(title="Telegram 대화방 목록")
        table.add_column("Chat ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Type", style="green")
        table.add_column("Username", style="magenta")

        count = 0
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            e_id, title, c_type, username = get_entity_info(entity)

            if search and search.lower() not in title.lower():
                continue

            table.add_row(str(e_id), title, c_type, f"@{username}" if username else "-")
            count += 1
            if count >= limit:
                break

        console.print(table)
        await client.disconnect()

    asyncio.run(_chats())


def determine_export_formats(
    md: bool, json_opt: bool, all_formats: bool, fmt_opt: Optional[str]
) -> tuple[bool, bool]:
    if all_formats or fmt_opt == "all":
        return True, True
    if json_opt or fmt_opt == "json":
        return md, True
    if md or fmt_opt == "md":
        return True, False
    # Default: markdown only
    return True, False


@app.command("export")
def export(
    chat: Optional[str] = typer.Argument(None, help="대상 대화방 ID, @username 또는 대화방 제목"),
    chat_opt: Optional[str] = typer.Option(None, "--chat", "-c", help="대상 대화방 (옵션 플래그)"),
    since: str = typer.Option("24h", "--since", "-s", help="수집 시작 시간 (예: 2h, 3d, yesterday, 2026-09-20 00:00)"),
    until: str = typer.Option("now", "--until", "-u", help="수집 종료 시간 (예: now, 2026-09-22 23:59)"),
    md: bool = typer.Option(False, "--md", help="마크다운(.md) 파일만 저장 (기본값)"),
    json_opt: bool = typer.Option(False, "--json", help="JSON(.json) 파일만 저장"),
    all_formats: bool = typer.Option(False, "--all", help="마크다운과 JSON 모두 저장"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="문서화 포맷 (md, json, all)"),
    output_dir: Path = typer.Option(Path("exports"), "--output-dir", "-o", help="문서 저장 디렉토리"),
    download_media: bool = typer.Option(False, "--download-media", help="미디어(사진/문서) 파일 다운로드 활성화"),
    limit: int = typer.Option(1000, "--limit", "-l", help="가져올 최대 메시지 수"),
) -> None:
    """지정된 기간 동안의 대화 기록을 수집하여 Markdown 또는 JSON으로 저장"""
    target_chat = chat or chat_opt
    if not target_chat:
        console.print("[bold red]오류:[/bold red] 대화방을 지정해야 합니다. (예: `telegram export '방이름'` 또는 `--chat '방이름'`)")
        raise typer.Exit(1)

    save_md, save_json = determine_export_formats(md, json_opt, all_formats, format)

    local_tz = datetime.now().astimezone().tzinfo or timezone.utc

    try:
        since_dt = parse_relative_or_absolute_time(since, local_tz)
        until_dt = parse_relative_or_absolute_time(until, local_tz)
    except ValueError as e:
        console.print(f"[bold red]시간 파싱 오류:[/bold red] {e}")
        raise typer.Exit(1)

    if since_dt >= until_dt:
        console.print("[bold red]오류:[/bold red] 시작 시간(--since)은 종료 시간(--until)보다 이전이어야 합니다.")
        raise typer.Exit(1)

    async def _export():
        client = get_client()
        await client.connect()
        if not await client.is_user_authorized():
            console.print("[bold red]로그인이 필요합니다.[/bold red] 먼저 `telegram login`을 실행하세요.")
            await client.disconnect()
            raise typer.Exit(1)

        try:
            entity = await resolve_target_entity(client, target_chat)
        except Exception as e:
            console.print(f"[bold red]대화방 조회 실패:[/bold red] {e}")
            await client.disconnect()
            raise typer.Exit(1)

        chat_id, chat_title, chat_type, chat_username = get_entity_info(entity)
        fmt_desc = "Markdown + JSON" if (save_md and save_json) else ("JSON" if save_json else "Markdown")
        console.print(
            f"수집 대상: [bold cyan]{chat_title}[/bold cyan] ({chat_type}, ID: {chat_id})\n"
            f"기간: [dim]{since_dt.strftime('%Y-%m-%d %H:%M')} ~ {until_dt.strftime('%Y-%m-%d %H:%M')}[/dim] (포맷: [green]{fmt_desc}[/green])"
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        media_dir = output_dir / "media" / str(chat_id)
        if download_media:
            media_dir.mkdir(parents=True, exist_ok=True)

        messages_data = []
        collected_count = 0

        # Telethon uses UTC for message.date
        since_utc = since_dt.astimezone(timezone.utc)
        until_utc = until_dt.astimezone(timezone.utc)

        raw_messages = []
        async for msg in client.iter_messages(entity, offset_date=until_utc, limit=limit):
            if msg.date > until_utc:
                continue
            if msg.date < since_utc:
                break
            raw_messages.append(msg)

        # Chronological order
        raw_messages.reverse()

        for msg in raw_messages:
            msg_local_date = msg.date.astimezone(local_tz)
            sender_id = msg.sender_id
            sender_name = "Unknown"
            sender_username = None

            if msg.sender:
                s_id, s_name, _, s_uname = get_entity_info(msg.sender)
                sender_id = s_id
                sender_name = s_name
                sender_username = s_uname

            media_info = None
            if msg.media:
                if isinstance(msg.media, MessageMediaPhoto):
                    media_type = "photo"
                elif isinstance(msg.media, MessageMediaDocument):
                    media_type = "document"
                else:
                    media_type = "other"

                media_info = {"type": media_type, "file_path": None}
                if download_media:
                    downloaded = await msg.download_media(file=media_dir)
                    if downloaded:
                        media_info["file_path"] = str(Path(downloaded).relative_to(output_dir))

            messages_data.append({
                "id": msg.id,
                "date": msg_local_date.isoformat(),
                "sender": {
                    "id": sender_id,
                    "name": sender_name,
                    "username": sender_username,
                },
                "reply_to_msg_id": msg.reply_to_msg_id,
                "text": msg.message or "",
                "media": media_info,
            })
            collected_count += 1

        await client.disconnect()

        now_str = datetime.now(local_tz).strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r"[^\w\-_\. ]", "_", chat_title).strip()
        base_filename = f"chat_{safe_title}_{chat_id}_{now_str}"

        # 1. Export JSON
        if save_json:
            json_file = output_dir / f"{base_filename}.json"
            export_payload = {
                "chat": {
                    "id": chat_id,
                    "title": chat_title,
                    "type": chat_type,
                    "username": chat_username,
                },
                "exported_at": datetime.now(local_tz).isoformat(),
                "time_range": {
                    "since": since_dt.isoformat(),
                    "until": until_dt.isoformat(),
                },
                "message_count": collected_count,
                "messages": messages_data,
            }
            json_file.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            console.print(f"[green]✓ JSON 저장 완료:[/green] {json_file}")

        # 2. Export Markdown
        if save_md:
            md_file = output_dir / f"{base_filename}.md"
            lines = [
                f"# 💬 대화 기록: {chat_title}",
                f"- **Chat ID**: `{chat_id}`",
                f"- **대화방 유형**: `{chat_type}`",
                f"- **수집 기간**: `{since_dt.strftime('%Y-%m-%d %H:%M:%S')}` ~ `{until_dt.strftime('%Y-%m-%d %H:%M:%S')}`",
                f"- **메시지 건수**: {collected_count}건",
                f"- **추출 일시**: `{datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S')}`",
                "",
                "---",
                "",
            ]

            # Fast index for replies
            msg_map = {m["id"]: m for m in messages_data}

            for m in messages_data:
                uname_tag = f" (@{m['sender']['username']})" if m["sender"]["username"] else ""
                lines.append(f"### 👤 {m['sender']['name']}{uname_tag} · *{m['date']}*")

                if m["reply_to_msg_id"] and m["reply_to_msg_id"] in msg_map:
                    replied = msg_map[m["reply_to_msg_id"]]
                    quote_text = replied["text"].replace("\n", " ").strip()
                    if len(quote_text) > 60:
                        quote_text = quote_text[:57] + "..."
                    lines.append(f"> **[{replied['sender']['name']}]**: {quote_text}")

                if m["text"]:
                    lines.append(m["text"])

                if m["media"]:
                    path = m["media"].get("file_path")
                    if path:
                        lines.append(f"\n📎 *[Attached: {path}]*")
                    else:
                        lines.append(f"\n📎 *[{m['media']['type'].capitalize()}]*")

                lines.append("")

            md_file.write_text("\n".join(lines), encoding="utf-8")
            console.print(f"[green]✓ Markdown 저장 완료:[/green] {md_file}")

        console.print(f"[bold cyan]총 {collected_count}개의 메시지를 성공적으로 내보냈습니다.[/bold cyan]")

    asyncio.run(_export())


def _read_dialog(
    chat: Optional[str] = typer.Argument(None, help="대상 대화방 ID, @username 또는 대화방 제목"),
    chat_opt: Optional[str] = typer.Option(None, "--chat", "-c", help="대상 대화방 (옵션 플래그)"),
    limit: int = typer.Option(20, "--limit", "-l", help="조회할 최근 메시지 수"),
    since: Optional[str] = typer.Option(None, "--since", "-s", help="시작 시간 필터링 (예: 2h, yesterday)"),
    pager: bool = typer.Option(False, "--pager", "-p", help="터미널 페이저(스크롤)로 보기"),
) -> None:
    """터미널에서 대화방의 최근 대화를 즉시 조회 (read, show, history 동일)"""
    target_chat = chat or chat_opt
    if not target_chat:
        console.print("[bold red]오류:[/bold red] 대화방을 지정해야 합니다. (예: `telegram read '방이름'` 또는 `telegram show '방이름'`)")
        raise typer.Exit(1)

    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    since_utc = None
    if since:
        try:
            since_dt = parse_relative_or_absolute_time(since, local_tz)
            since_utc = since_dt.astimezone(timezone.utc)
        except ValueError as e:
            console.print(f"[bold red]시간 파싱 오류:[/bold red] {e}")
            raise typer.Exit(1)

    async def _run():
        client = get_client()
        await client.connect()
        if not await client.is_user_authorized():
            console.print("[bold red]로그인이 필요합니다.[/bold red] 먼저 `telegram login`을 실행하세요.")
            await client.disconnect()
            raise typer.Exit(1)

        try:
            entity = await resolve_target_entity(client, target_chat)
        except Exception as e:
            console.print(f"[bold red]대화방 조회 실패:[/bold red] {e}")
            await client.disconnect()
            raise typer.Exit(1)

        chat_id, chat_title, chat_type, _ = get_entity_info(entity)
        me = await client.get_me()
        my_id = me.id if me else 0

        raw_messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            if since_utc and msg.date < since_utc:
                break
            raw_messages.append(msg)

        await client.disconnect()
        raw_messages.reverse()

        def render_messages():
            console.print(f"\n[bold cyan]💬 {chat_title}[/bold cyan] [dim]({chat_type}, ID: {chat_id} | 최근 {len(raw_messages)}건)[/dim]\n" + "─" * 60)

            # Map for reply text lookup
            msg_map = {m.id: m for m in raw_messages}

            for msg in raw_messages:
                msg_local = msg.date.astimezone(local_tz)
                time_str = msg_local.strftime("%m-%d %H:%M")

                is_me = (msg.sender_id == my_id)
                sender_name = "나" if is_me else "Unknown"
                if not is_me and msg.sender:
                    _, s_name, _, _ = get_entity_info(msg.sender)
                    sender_name = s_name

                sender_style = "bold green" if is_me else "bold yellow"

                # Reply quote
                if msg.reply_to_msg_id and msg.reply_to_msg_id in msg_map:
                    replied = msg_map[msg.reply_to_msg_id]
                    rep_name = "나" if replied.sender_id == my_id else "상대방"
                    if replied.sender:
                        _, r_name, _, _ = get_entity_info(replied.sender)
                        rep_name = r_name
                    rep_text = (replied.message or "").replace("\n", " ").strip()
                    if len(rep_text) > 40:
                        rep_text = rep_text[:37] + "..."
                    console.print(f"  [dim]↳ [{rep_name}]: {rep_text}[/dim]")

                # Header line
                console.print(f"[{sender_style}]{sender_name}[/{sender_style}] [dim]({time_str})[/dim]")

                # Text content
                if msg.message:
                    # Indent slightly for clean look
                    for line in msg.message.split("\n"):
                        console.print(f"  {line}")

                # Media tag
                if msg.media:
                    m_type = "사진" if isinstance(msg.media, MessageMediaPhoto) else "문서/파일"
                    console.print(f"  [dim magenta]📎 [{m_type}][/dim magenta]")

                console.print()

        if pager:
            with console.pager(styles=True):
                render_messages()
        else:
            render_messages()

    asyncio.run(_run())


# Register read, show, and history commands
app.command("read", help="터미널에서 대화방의 최근 대화를 즉시 조회")(_read_dialog)
app.command("show", help="터미널에서 대화방의 최근 대화를 즉시 조회 (read와 동일)")(_read_dialog)
app.command("history", help="터미널에서 대화방의 과거 대화기록 조회 (read와 동일)")(_read_dialog)


@app.command("send")
def send(
    chat: Optional[str] = typer.Argument(None, help="대상 대화방 ID, @username 또는 대화방 제목"),
    chat_opt: Optional[str] = typer.Option(None, "--chat", "-c", help="대상 대화방 (옵션 플래그)"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="보낼 메시지 본문"),
    file: Optional[Path] = typer.Option(None, "--file", help="본문으로 보낼 텍스트/마크다운 파일 경로"),
    attach: Optional[Path] = typer.Option(None, "--attach", help="첨부할 사진 또는 문서 파일 경로"),
    silent: bool = typer.Option(False, "--silent", help="무음 메시지로 전송"),
) -> None:
    """지정된 대화방으로 메시지 또는 파일 발송 (4096자 초과 시 자동 분할)"""
    target_chat = chat or chat_opt
    if not target_chat:
        console.print("[bold red]오류:[/bold red] 대화방을 지정해야 합니다. (예: `telegram send '방이름' --text '안녕'`)")
        raise typer.Exit(1)
    if not text and not file and not attach:
        console.print("[bold red]오류:[/bold red] --text, --file 또는 --attach 중 적어도 하나를 지정해야 합니다.")
        raise typer.Exit(1)

    message_content = ""
    if file:
        if not file.exists():
            console.print(f"[bold red]오류:[/bold red] 파일 '{file}'을 찾을 수 없습니다.")
            raise typer.Exit(1)
        message_content = file.read_text(encoding="utf-8")
    elif text:
        message_content = text

    async def _send():
        client = get_client()
        await client.connect()
        if not await client.is_user_authorized():
            console.print("[bold red]로그인이 필요합니다.[/bold red] 먼저 `telegram-tools login`을 실행하세요.")
            await client.disconnect()
            raise typer.Exit(1)

        try:
            entity = await resolve_target_entity(client, target_chat)
        except Exception as e:
            console.print(f"[bold red]대화방 조회 실패:[/bold red] {e}")
            await client.disconnect()
            raise typer.Exit(1)

        _, chat_title, _, _ = get_entity_info(entity)

        # 1. Attachment send
        if attach:
            if not attach.exists():
                console.print(f"[bold red]오류:[/bold red] 첨부 파일 '{attach}'을 찾을 수 없습니다.")
                await client.disconnect()
                raise typer.Exit(1)

            # ponytail: single caption if message fits in 1024 chars, otherwise send file then text chunks
            caption = message_content if len(message_content) <= 1024 else None
            await client.send_file(entity, file=str(attach), caption=caption, silent=silent, parse_mode="md")
            console.print(f"[green]✓ 첨부 파일 전송 완료:[/green] {attach.name} -> {chat_title}")
            if caption:
                await client.disconnect()
                return

        # 2. Text message send (split into 4000-char chunks)
        if message_content:
            chunks = chunk_text(message_content, max_len=4000)
            for i, chunk in enumerate(chunks, 1):
                try:
                    await client.send_message(entity, chunk, parse_mode="md", silent=silent)
                except errors.FloodWaitError as e:
                    console.print(f"[yellow]Rate limit 감지: {e.seconds}초 대기 중...[/yellow]")
                    await asyncio.sleep(e.seconds + 1)
                    await client.send_message(entity, chunk, parse_mode="md", silent=silent)

                if len(chunks) > 1:
                    console.print(f"[dim]메시지 조각 전송 완료 ({i}/{len(chunks)})[/dim]")

            console.print(f"[bold green]✓ 메시지 전송 완료[/bold green] -> [bold cyan]{chat_title}[/bold cyan]")

        await client.disconnect()

    asyncio.run(_send())


@app.command("logout")
def logout() -> None:
    """로컬 세션 파일 삭제 및 로그아웃"""
    deleted = False
    for f in DATA_DIR.glob("telegram_user.session*"):
        try:
            f.unlink()
            deleted = True
        except OSError as e:
            console.print(f"[yellow]경고: {f.name} 삭제 실패 ({e})[/yellow]")

    if deleted:
        console.print("[bold green]✓ 세션 파일이 안전하게 삭제되었습니다.[/bold green]")
    else:
        console.print("[yellow]삭제할 세션 파일이 없습니다.[/yellow]")


if __name__ == "__main__":
    app()
