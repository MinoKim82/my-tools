# telegram-tools AI Agent 개발 및 유지보수 가이드 (SSOT)

이 문서는 `tools/telegram-tools` 도구를 개발, 유지보수, 리팩토링하는 AI 에이전트를 위한 서브프로젝트 전용 아키텍처 명세서이자 개발 지침서입니다.  
프로젝트 전역 규칙은 루트 [AGENTS.md](../../AGENTS.md)를 참조하십시오.

---

## 1. 서브프로젝트 개요 및 설계 철학

`telegram-tools`는 텔레그램(Telegram)의 과거 대화 기록을 특정 기간 단위로 정밀하게 수집하여 구조화된 문서(JSON, Markdown)로 내보내고, 마크다운 메시지 및 대용량 파일을 전송하는 완전 자립형(Stand-alone) CLI 유틸리티입니다.

### 1.1 핵심 설계 목표
- **과거 대화 소급 아카이빙 (MTProto User API 기반)**:
  - 텔레그램 공식 Bot API는 과거 대화기록 조회 API를 제공하지 않으므로, `Telethon` (MTProto Client API) 기반의 유저 세션을 사용하여 내가 속한 모든 개인톡, 비공개 그룹, 슈퍼그룹, 채널의 대화를 완벽하게 수집합니다.
- **인간 및 LLM 최적화 듀얼 문서화 포맷**:
  - LLM 요약 프롬프트와 옵시디언/마크다운 뷰어에 적합한 타임라인형 Markdown(`.md`)과, 데이터 가공 및 분석을 위한 완전한 메타데이터가 담긴 정형 JSON(`.json`)을 동시 생성합니다.
- **경량 고속 수집 및 선택적 미디어 다운로드**:
  - 일상적인 회의록/대화 요약 시에는 텍스트와 메타데이터만 즉각 수집하고, 대용량 미디어(사진, 보이스, 문서)는 `--download-media` 플래그 지정 시에만 스트리밍 다운로드하여 네트워크 대역폭과 디스크를 보호합니다.
- **지능형 메시지 분할 전송 (Smart 4096 Chunking)**:
  - 텔레그램의 단일 메시지 길이 제한(4,096자)을 고려하여, 긴 보고서 파일 전송 시 단락(`\n\n`)과 문장 단위를 보존하며 지능적으로 분할 발송합니다.

---

## 2. 아키텍처 및 모듈 구성 (`src/`)

```text
tools/telegram-tools/
├── README.md                 # 사용자 및 개발자용 종합 가이드
├── AGENTS.md                 # 서브프로젝트 전용 AI 개발 지침서 (본 문서)
├── skill/
│   └── SKILL.md              # AI 에이전트 런타임 스킬 명세서
└── src/
    ├── pyproject.toml        # 의존성 정의 (telethon, typer, rich, python-dateutil, pydantic)
    ├── .env.example          # 환경변수 템플릿
    ├── telegram-tools.sh     # CLI 전역 심링크 실행 래퍼
    ├── main.py               # Typer 기반 CLI 진입점 (chats, export, send, login, status, logout)
    ├── core/
    │   ├── config.py         # 환경변수, 상수, 디렉토리 경로 정의
    │   ├── client.py         # Telethon TelegramClient 생명주기 및 세션 매니저
    │   ├── time_parser.py    # 상대 시간(2h, 3d, yesterday) 및 절대 시간 파서
    │   ├── exporter.py       # 대화 기록 수집, JSON 및 Markdown 직렬화 엔진
    │   └── sender.py         # 메시지 청킹(4096자), 마크다운 파싱, 첨부파일 전송 엔진
    ├── data/                 # 세션 파일 저장소 (*.session, .gitignore 필수)
    ├── exports/              # 내보낸 대화기록 기본 저장소
    └── tests/                # 단위 테스트 (pytest)
```

### 2.1 주요 모듈별 역할과 책임

1. **`core/config.py`**:
   - `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE` 환경변수 로드 (`python-dotenv`).
   - 기본 경로 상수 정의:
     - `SESSION_PATH`: `data/telegram_user.session`
     - `DEFAULT_EXPORTS_DIR`: `exports/`
     - `TIMEZONE`: `Asia/Seoul` (기본 타임존)
   - 필수 환경변수 누락 시 친절한 안내 메시지와 함께 조기 종료(Fail-Fast).

2. **`core/client.py` (`TelegramClientManager`)**:
   - `Telethon`의 `TelegramClient` 인스턴스 팩토리 및 컨텍스트 매니저(`async with`).
   - 대화형 로그인(`client.start(phone=...)`) 및 2FA 비밀번호 입력 처리.
   - 텔레그램 `FloodWaitError` 발생 시 `seconds`만큼 자동 대기 후 재시도하는 공통 데코레이터/핸들러 내장.
   - 대상 대화방(Entity) 검색 로직: Chat ID(정수), `@username`, 또는 대화방 타이틀 부분 문자열 매칭 지원.

3. **`core/time_parser.py` (`TimeRangeParser`)**:
   - 다양한 시간 입력 문자열을 Python `datetime` (타임존 인식: KST/UTC) 객체로 파싱:
     - 상대 시간: `10m`, `2h`, `24h`, `3d`, `1w`, `today`, `yesterday`
     - 절대 시간: `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM:SS`
   - 수집 범위 `(since_dt, until_dt)`를 검증하여 `since_dt < until_dt` 규칙 보장.

4. **`core/exporter.py` (`ChatExporter`)**:
   - `client.iter_messages(entity, offset_date=..., reverse=True)`를 활용하여 지정된 기간의 메시지를 시간순 스트리밍 수집.
   - 답글(Reply) 관계 추적: 이전 메시지 인용(quote) 데이터 추출.
   - Pydantic 모델 `ExportPayload`, `ChatMessage`, `ChatSender`를 기반으로 무결성 보장.
   - JSON 포맷 직렬화 (`chat_export_<chat_id>_<timestamp>.json`).
   - 타임라인형 Markdown 렌더링 (`chat_export_<chat_id>_<timestamp>.md`).
   - `--download-media` 활성화 시 사진, 음성, 문서 스트리밍 다운로드 (`exports/media/<chat_id>/...`).

5. **`core/sender.py` (`MessageSender`)**:
   - 단일 텍스트, 파일 본문, 미디어 첨부 발송 처리.
   - **스마트 청커 (Smart Message Chunker)**:
     - 4,096자 초과 시 문단(`\n\n`) -> 줄바꿈(`\n`) -> 문장 마침표(`. `) 순으로 분할 지점을 탐색하여 문맥이 끊기지 않도록 분할 발송.
   - Telethon의 `parse_mode="md"` 지원.
   - `silent=True` 옵션 지원.

---

## 3. 핵심 알고리즘 및 비직관적 패턴 (Non-Obvious Patterns & Gotchas)

### 3.1 Rate Limit (`FloodWaitError`) 방어 정책
- 텔레그램 MTProto API는 단시간에 대량의 메시지 조회나 전송 시 `telethon.errors.FloodWaitError`를 발생시킵니다.
- **해결 원칙**:
  ```python
  from telethon.errors import FloodWaitError
  import asyncio

  async def safe_telegram_call(coro_func, *args, **kwargs):
      max_retries = 3
      for attempt in range(max_retries):
          try:
              return await coro_func(*args, **kwargs)
          except FloodWaitError as e:
              if e.seconds > 60:
                  # 60초 초과 대기 시 강제 중단하고 사용자에게 에러 보고
                  raise RuntimeError(f"Telegram FloodWait too long: {e.seconds}s")
              await asyncio.sleep(e.seconds + 1)
  ```

### 3.2 텔레그램 대화방 ID 체계 (Entity ID Caveats)
- 텔레그램의 대화방 ID는 유형에 따라 접두사가 다릅니다:
  - 개인 사용자 (User): 양수 정수 (예: `987654321`)
  - 일반 그룹 (Basic Group): 음수 정수 (예: `-12345678`)
  - 슈퍼그룹 및 채널 (Supergroup/Channel): `-100` 접두사 음수 (예: `-1001234567890`)
- **주의사항**: CLI 인자로 음수 ID(예: `-1001234567890`)를 전달할 때 Typer나 Bash에서 옵션 플래그로 오인될 수 있습니다.  
  따라서 `--chat "-1001234567890"` 또는 `--chat=-1001234567890` 형태로 처리되도록 허용하고, 정수 파싱 실패 시 대화방 제목 문자열 검색으로 자동 폴백해야 합니다.

### 3.3 타임존 일관성 (UTC vs KST)
- 텔레그램 메시지의 `message.date` 속성은 **항상 UTC 타임존**을 가집니다.
- 사용자가 지정하는 `--since "2026-09-20 00:00"`는 기본적으로 **로컬 타임존(Asia/Seoul)** 기준입니다.
- **처리 원칙**:
  - `since`와 `until` 입력을 파싱할 때 `ZoneInfo("Asia/Seoul")`을 적용한 뒤, 텔레그램 API와 비교 시에는 UTC로 변환하여 비교하거나, 두 타임스탬프 모두 타임존 인식(Timezone-aware) 상태로 통일하여 비교해야 합니다.
  - 출력되는 Markdown 및 JSON의 타임스탬프는 사용자 친화적인 KST(`+09:00`) 표기를 기본으로 합니다.

### 3.4 Telethon 세션 SQLite 동시성 락 (`database is locked`)
- Telethon의 `telegram_user.session`은 SQLite 파일 기반입니다.
- 두 개 이상의 프로세스(예: 백그라운드 크론과 CLI 명령)가 동일한 `.session` 파일에 동시에 쓰기 접근을 시도하면 `sqlite3.OperationalError: database is locked`가 발생합니다.
- **주의사항**: 모든 CLI 명령어는 클라이언트 작업 완료 후 반드시 세션 연결을 닫고(`await client.disconnect()`), 세션 파일 디렉토리에 잠금 충돌이 발생하지 않도록 단일 작업 단위로 실행을 완료해야 합니다.

### 3.5 4,096자 스마트 분할 알고리즘
- 텔레그램 단일 메시지 한도는 4,096자(바이트가 아닌 유니코드 문자 수)입니다.
- 코드 블록(```` ``` ````) 중간에서 단순 분할되면 마크다운 문법이 깨지므로, 가능한 줄바꿈(`\n\n`) 지점에서 자르고, 분할된 각 조각에 번호(`(1/3)`, `(2/3)`)를 붙이지 않고 자연스럽게 연속 전송하거나 안전한 문맥 분할을 보장합니다.

---

## 4. 에이전트 준수 가이드라인 (Crucial Guardrails for Agents)

### 4.1 Do's
- **가상환경 및 툴체인은 반드시 `uv` 표준을 사용합니다.** (`uv sync`, `uv run python ...`)
- **비밀값 및 세션 격리**: `.env`, `.env.example`, `data/*.session`의 배제 상태를 항상 점검합니다.
- **상대 경로 준수**: 저장소 내 모든 문서 링크 및 산출물 파일 경로는 순수 상대 경로를 사용합니다.
- **정형 출력과 시각 출력 분리**: 인간 사용자를 위해 `rich.console` 및 `rich.table`을 사용하되, 파이프라인 연동(`--json`) 지원 시 머신 판독용 JSON만 출력하도록 설계합니다.

### 4.2 Don'ts
- **절대 커밋 금지**:
  - `.env` 파일 (실제 API ID, Hash, 전화번호)
  - `data/*.session` 파일 (인증된 로그인 세션 바이너리)
  - `exports/` 내 실제 대화 내용 파일
- **Bot API 혼용 금지**:
  - 과거 대화 수집 요구사항이 존재하므로 Bot Token 전용 모드로 회귀하지 않습니다. (Telethon MTProto User API 단일화 원칙 유지)
- **과도한 추상화 금지**:
  - YAGNI 원칙에 따라 현재 요구사항(수집/문서화, 발송, 대화방 검색)에 집중하고, 복잡한 플러그인 시스템이나 불필요한 계층 분리를 만들지 않습니다.

---

## 5. 테스트 및 검증 지침 (Testing & Verification)

### 5.1 단위 테스트 범위 (`src/tests/`)
1. **`test_time_parser.py`**:
   - 상대 시간 문자열(`2h`, `24h`, `yesterday`, `3d`)이 정확한 시간 차이(timedelta)로 변환되는지 검증.
   - 잘못된 형식 입력 시 유효성 검증 에러 발생 확인.
2. **`test_chunker.py`**:
   - 4,096자 초과 텍스트 및 마크다운 문서가 문맥을 해치지 않고 올바른 크기로 청킹되는지 검증.
3. **`test_exporter_format.py`**:
   - 목(Mock) 메시지 객체를 주입하여 JSON 및 Markdown 직렬화 결과물의 필드 규격과 포맷 일치 여부 검증.

### 5.2 테스트 실행 명령
```bash
cd tools/telegram-tools/src
uv run pytest tests/ -v
```

---

## 6. 개발 및 배포 워크플로우 (Step-by-Step)

1. `tools/telegram-tools/src/pyproject.toml` 작성 및 `uv sync` 실행.
2. `tools/telegram-tools/src/.env.example` 및 `.gitignore` 작성.
3. `core/config.py`, `core/time_parser.py`, `core/client.py`, `core/exporter.py`, `core/sender.py` 구현.
4. `main.py` CLI 인터페이스 구현 (Typer 명령어 바인딩).
5. `tools/telegram-tools/src/telegram-tools.sh` 래퍼 스크립트 작성 (`chmod +x`).
6. `tools/telegram-tools/skill/SKILL.md` 에이전트 런타임 스킬 명세서 작성.
7. 단위 테스트 작성 및 `uv run pytest` 검증.
8. 루트 `Makefile`을 통해 `make link tool=telegram-tools` 및 `make link-skill tool=telegram-tools` 테스트.
9. 루트 `README.md`의 도구 카탈로그(Tools Catalog) 표에 `telegram-tools` 추가.
10. Git 상태 확인 후 `feat(telegram-tools): add telegram-tools scaffolding, documentation and core logic` 커밋.
