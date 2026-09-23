# telegram-tools

텔레그램(Telegram) 채팅방의 기간별 대화 기록을 추출하여 문서화(JSON, Markdown)하고, 메시지 및 첨부파일을 전송하는 전용 자동화 CLI 유틸리티입니다.

> 태그: `[CLI]` `[SCRIPT]` `[TELEGRAM]`

---

## 📌 주요 특징 및 기능

1. **기간별 대화 기록 추출 및 문서화 (`export`)**:
   - 특정 대화방(개인 채팅, 비공개 그룹, 슈퍼그룹, 공개 채널)의 대화 기록을 원하는 기간만큼 추출.
   - **유연한 시간 범위 지정**:
     - 상대 시간 지원: `--since "2h"`, `--since "24h"`, `--since "3d"`, `--since "yesterday"`
     - 절대 시간 지원: `--since "2026-09-20 00:00" --until "2026-09-23 18:00"` (ISO 8601 및 YYYY-MM-DD HH:MM)
   - **듀얼 문서화 포맷**:
     - **JSON (`.json`)**: 메시지 ID, UTC/KST 타임스탬프, 발신자 메타데이터, 답글 인용(reply_to), 첨부 미디어 정보 등 구조화된 데이터 보존.
     - **Markdown (`.md`)**: 가독성 높은 타임라인 블록, 답글 인용문(`> quote`), 미디어 배지 표기 등 LLM 요약 프롬프트 및 문서 보관에 최적화.
   - **경량 텍스트 중심 + 미디어 선택 다운로드**: 기본은 텍스트/메타데이터만 고속 수집하며, `--download-media` 지정 시 사진/문서/음성 파일까지 로컬 저장 및 상대 경로 링크.

2. **메시지 및 파일 전송 (`send`)**:
   - **인라인 메시지**: `--text "..."`로 즉각 전송 (Markdown/HTML 서식 파싱 지원).
   - **파일 본문 전송**: `--file report.md`로 긴 텍스트 문서를 전송하며, 텔레그램 메시지 제한(4,096자) 초과 시 단락/문장 단위로 자동 분할 전송.
   - **미디어/문서 첨부**: `--attach <file_path>`로 사진, PDF, ZIP 등 임의의 파일 첨부 전송.
   - **무음 전송**: `--silent` 플래그로 상대방에게 알림음 없이 조용히 메시지 전달.

3. **대화방 검색 및 탐색 (`chats`)**:
   - 내 계정에 속한 활성 대화방(채팅방명, Chat ID, Username, 대화방 유형)을 실시간 검색 및 테이블 출력.
   - 사용자가 방 ID를 매번 기억하지 않고도 대화방 이름(부분 일치)이나 `@username`, Chat ID로 손쉽게 지정 가능.

4. **MTProto User API (Telethon) 기반 고속 아카이빙**:
   - Bot API의 치명적 한계(과거 대화기록 소급 조회 불가, Privacy Mode)를 극복하여, 사용자가 속한 모든 대화방의 과거 대화기록을 완벽하게 수집.
   - 텔레그램 Rate Limit(`FloodWaitError`) 자동 감지 및 지수 백오프 안전 대기 지원.

---

## 🛠️ 준비 사항 및 설치

### 1. Telegram API 자격 증명 준비
텔레그램 MTProto 클라이언트를 실행하려면 `api_id`와 `api_hash`가 필요합니다 (무료 발급):
1. [https://my.telegram.org](https://my.telegram.org)에 접속하여 전화번호로 로그인합니다.
2. **API development tools** 메뉴로 이동합니다.
3. 임의의 App title과 Short name을 입력하여 앱을 생성하고, 발급된 **`api_id`**와 **`api_hash`**를 복사합니다.

### 2. 도구 환경 설치
```bash
# 1. 도구 src 디렉토리로 이동
cd tools/telegram-tools/src

# 2. 의존성 설치 및 가상환경 생성 (uv 표준)
uv sync

# 3. 환경변수 파일 설정 (.env)
cp .env.example .env
# .env 파일을 열어 TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE 입력
```

`.env` 설정 예시:
```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
TELEGRAM_PHONE=+821012345678
```

---

## 🚀 전역 등록 및 빠른 실행 (Quick Start)

저장소 루트(`my-tools/`)에서 Makefile을 통해 CLI 및 에이전트 스킬로 즉시 등록할 수 있습니다:

```bash
# 저장소 루트(my-tools/)에서 실행
make link tool=telegram-tools as=telegram   # ~/.local/bin/telegram 단축 CLI 심링크
make link-skill tool=telegram-tools         # ~/.gemini/config/skills/telegram-tools 스킬 심링크
```

> 💡 `as=telegram` 옵션을 주면 터미널에서 `telegram-tools` 대신 짧은 `telegram` 명령어로 호출할 수 있습니다.

### 최초 세션 인증 (1회 수행)
```bash
# 대화형 CLI를 통한 로그인 및 세션 파일 생성
telegram-tools login
```
- 터미널에 텔레그램 앱으로 수신된 인증 코드(숫자)를 입력합니다.
- 2단계 인증(2FA Password)이 설정되어 있는 경우 비밀번호를 입력하면 `src/data/telegram_user.session`에 세션이 안전하게 저장됩니다.

---

## 📖 CLI 명령어 가이드

### 1. 대화방 목록 조회 및 검색 (`chats`)
```bash
# 최근 활성 대화방 20개 조회
telegram-tools chats

# 대화방 이름 검색
telegram-tools chats --search "개발"

# 최대 조회 개수 설정
telegram-tools chats --limit 50
```

출력 예시:
```text
┌─────────────┬──────────────────────┬─────────────┬─────────────────┐
│ Chat ID     │ Title                │ Type        │ Username        │
├─────────────┼──────────────────────┼─────────────┼─────────────────┤
│ -1001234567 │ 팀 프로젝트 회의방   │ supergroup  │ @proj_dev_room  │
│ 987654321   │ 홍길동               │ user        │ @gildong        │
│ -1009876543 │ 사내 공지 채널       │ channel     │ -               │
└─────────────┴──────────────────────┴─────────────┴─────────────────┘
```

---

### 2. 대화 기록 터미널 즉시 조회 (`read` / `show` / `history`)

파일 저장 없이 터미널 화면에서 대화방의 최근 대화를 즉시 확인합니다:

```bash
# 대화방의 최근 20개 메시지 출력 (위치 인자 지원)
telegram read "팀 프로젝트"

# 최근 50개 메시지 터미널 페이저(less 스크롤)로 보기
telegram show "사내 공지" --limit 50 --pager

# 특정 시간 이후 대화만 조회
telegram history "@proj_dev_room" --since "2h"
```

---

### 3. 대화 기록 추출 및 문서화 (`export`)

지정한 대화방에서 특정 기간 사이의 메시지를 추출하여 Markdown 또는 JSON 파일로 저장합니다.

```bash
# 1. 최근 24시간 대화 추출 (기본값: Markdown .md 파일만 1개 생성)
telegram export "팀 프로젝트" --since "24h"

# 2. JSON 데이터 포맷으로만 저장
telegram export "팀 프로젝트" --since "yesterday" --json

# 3. Markdown과 JSON 파일 둘 다 생성
telegram export 777000 --since "2h" --all

# 4. 특정 날짜 범위 지정 및 미디어 파일까지 다운로드
telegram export -1001234567 --since "2026-09-20 00:00" --until "2026-09-22 23:59" --download-media --output-dir "./logs"
```

#### 주요 옵션:
| 옵션 | 단축키 | 기본값 | 설명 |
|---|---|---|---|
| `[chat]` | | *(필수)* | 위치 인자로 대화방 이름, ID, 또는 `@username` 바로 입력 (또는 `--chat` 플래그 사용) |
| `--since` | `-s` | `"24h"` | 수집 시작 시간 (상대 시간: `2h`, `24h`, `3d`, `yesterday` / 절대 시간: `YYYY-MM-DD HH:MM`) |
| `--until` | `-u` | `"now"` | 수집 종료 시간 (기본값: 현재 시각) |
| `--md` | | `True` | 마크다운(`.md`) 파일 저장 (기본값) |
| `--json` | | `False` | JSON(`.json`) 파일 저장 |
| `--all` | | `False` | 마크다운과 JSON 모두 저장 |
| `--output-dir` | `-o` | `"exports"` | 문서 및 미디어가 저장될 디렉토리 경로 |
| `--download-media` | | `False` | 사진/문서/음성 미디어 파일 다운로드 활성화 |
| `--limit` | `-l` | `1000` | 가져올 최대 메시지 수 제한 |

---

### 3. 메시지 발송 (`send`)

```bash
# 1. 인라인 텍스트 발송 (Markdown 서식 자동 적용)
telegram-tools send --chat -1001234567 --text "**[긴급 공지]** 서버 점검이 22:00에 시작됩니다."

# 2. 마크다운 보고서 파일 전송 (4096자 초과 시 자동 분할 전송)
telegram-tools send --chat "@proj_dev_room" --file "meeting_summary.md"

# 3. 사진 또는 문서 첨부 발송
telegram-tools send --chat 987654321 --text "요청하신 보고서 전달드립니다." --attach "report.pdf"

# 4. 무음(Silent) 발송
telegram-tools send --chat -1001234567 --text "새벽 배치 작업이 완료되었습니다." --silent
```

---

### 4. 세션 상태 점검 및 로그아웃
```bash
# 현재 로그인 세션 상태 및 내 계정 정보 확인
telegram-tools status

# 세션 파일 삭제 및 로그아웃
telegram-tools logout
```

---

## 📄 산출물 문서 규격

### 1. Markdown 포맷 (`.md`)
```markdown
# 💬 대화 기록: 팀 프로젝트 회의방
- **Chat ID**: `-1001234567`
- **대화방 유형**: `supergroup`
- **수집 기간**: `2026-09-20 00:00:00` ~ `2026-09-21 00:00:00` (KST)
- **메시지 건수**: 42건
- **추출 일시**: `2026-09-23 21:00:00`

---

### 👤 홍길동 (@gildong) · *2026-09-20 10:15:30*
오늘 배포 예정인 신규 기능 확인 부탁드립니다.

### 👤 이순신 (@sunshin) · *2026-09-20 10:16:05*
> **[홍길동]**: 오늘 배포 예정인 신규 기능 확인 부탁드립니다.
스테이징 서버 검증 완료했습니다! 🚀

📎 *[Photo: media/photo_102.jpg]*
```

### 2. JSON 포맷 (`.json`)
```json
{
  "chat": {
    "id": -1001234567,
    "title": "팀 프로젝트 회의방",
    "type": "supergroup",
    "username": "proj_dev_room"
  },
  "exported_at": "2026-09-23T21:00:00+09:00",
  "time_range": {
    "since": "2026-09-20T00:00:00+09:00",
    "until": "2026-09-21T00:00:00+09:00"
  },
  "message_count": 42,
  "messages": [
    {
      "id": 101,
      "date": "2026-09-20T10:15:30+09:00",
      "sender": {
        "id": 111222333,
        "name": "홍길동",
        "username": "gildong"
      },
      "reply_to_msg_id": null,
      "text": "오늘 배포 예정인 신규 기능 확인 부탁드립니다.",
      "media": null
    }
  ]
}
```

---

## 🔒 보안 및 개인정보 유의사항
- `src/data/*.session` 파일은 텔레그램 로그인 권한을 완전히 보유한 민감한 세션 파일입니다.
- `.env` 및 `*.session` 파일은 `.gitignore`에 등록되어 절대 Git에 커밋되지 않도록 보호됩니다.
- 본 도구는 로컬 환경에서 직접 실행되며 어떤 외부 제3자 서버로도 자격 증명이나 대화 내용을 전송하지 않습니다.
