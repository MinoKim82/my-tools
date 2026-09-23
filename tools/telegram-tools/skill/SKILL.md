---
name: telegram-tools
description: Export Telegram chat history between specific time ranges into JSON and Markdown, send Telegram messages and file attachments, search and list active chat rooms, or check Telegram session status using the telegram-tools CLI. Trigger this skill whenever the user asks to extract Telegram chats, archive conversations, send a message or report to Telegram, search Telegram dialogs, or check Telegram connection (e.g., "텔레그램 대화 가져와줘", "텔레그램 대화기록 백업해", "최근 24시간 텔레그램 채팅 요약해줘", "텔레그램 방에 메시지 보내줘", "이 마크다운 파일 텔레그램으로 전송해", "텔레그램 채팅방 목록 보여줘", "텔레그램 세션 상태 확인해줘").
---

# Telegram Tools Skill

텔레그램(Telegram) 대화방의 기간별 대화 기록을 추출하여 Markdown 및 JSON으로 문서화하고, 메시지 또는 파일을 전송하는 에이전트 스킬입니다.

---

## 🚫 1. Agent Role & Guardrails (에이전트 권한 및 안전 규칙)

- **허용된 명령어**:
  - `status`: 현재 텔레그램 계정 세션 상태 및 내 정보 확인
  - `chats`: 대화방 목록 조회 및 ID/Username 검색
  - `read` / `show`: 대화방의 최근 대화 즉시 조회 (터미널 뷰어)
  - `export`: 특정 대화방의 기간별 대화 기록 추출 및 문서화 (기본: Markdown, 옵션: JSON, All)
  - `send`: 메시지 텍스트, 마크다운 보고서 파일, 또는 첨부파일 전송
  - `logout`: 세션 파일 삭제
- **사용자 개입 필요 명령어 (`login`)**:
  - `login`은 텔레그램 앱으로 전송되는 인증 코드와 2FA 비밀번호 입력을 요구하므로 에이전트가 직접 실행하지 않고 사용자에게 직접 터미널 실행을 안내합니다.
- **실행 진입점**:
  - 시스템 전역 등록 시: `telegram <command>` 또는 `telegram-tools <command>`
  - 로컬 스크립트 호출 시: `tools/telegram-tools/src/telegram-tools.sh <command>`

---

## 🚀 2. Execution Commands (실행 명령어 가이드)

### 1) 대화방 목록 검색 및 ID 조회 (`chats`)
대화방 ID나 정확한 이름을 확인하기 위해 먼저 목록을 조회할 수 있습니다:
```bash
# 최근 대화방 20개 조회
telegram chats

# 특정 키워드로 대화방 검색
telegram chats --search "개발"
```

### 2) 터미널에서 대화 즉시 조회 (`read` / `show`)
파일 저장 없이 터미널 화면에서 대화를 바로 확인합니다:
```bash
# 최근 20개 대화 바로 출력 (위치 인자 지원)
telegram read "팀 프로젝트"

# 최근 50개 대화 터미널 페이저(스크롤)로 보기
telegram show "사내 공지" --limit 50 --pager

# 특정 시간 이후 대화만 조회
telegram read "@username" --since "2h"
```

### 3) 기간별 대화 기록 추출 및 문서화 (`export`)
채팅방 이름(부분 일치), Chat ID, 또는 `@username`을 지정하여 대화 기록을 추출합니다:

```bash
# 최근 24시간 동안의 대화 추출 (기본값: Markdown .md 파일만 생성)
telegram export "대화방명_또는_ID" --since "24h"

# JSON 파일만 단독 저장
telegram export -1001234567 --since "yesterday" --json

# Markdown과 JSON 파일 둘 다 생성
telegram export "회의방" --since "3d" --all

# 미디어(사진/문서) 파일까지 다운로드
telegram export "회의방" --since "24h" --download-media
```

#### 주요 옵션:
| 옵션 | 단축키 | 기본값 | 설명 |
|---|---|---|---|
| `[chat]` | | *(필수)* | 대화방 이름, ID(정수), 또는 `@username` |
| `--since` | `-s` | `"24h"` | 시작 시각 (`2h`, `24h`, `3d`, `yesterday`, `YYYY-MM-DD HH:MM`) |
| `--until` | `-u` | `"now"` | 종료 시각 (`now`, `YYYY-MM-DD HH:MM`) |
| `--md` | | `True` | 마크다운(`.md`) 파일 저장 (기본값) |
| `--json` | | `False` | JSON(`.json`) 파일 저장 |
| `--all` | | `False` | 마크다운과 JSON 모두 저장 |
| `--output-dir` | `-o` | `"exports"` | 문서 저장 디렉토리 |
| `--download-media` | | `False` | 사진/문서/음성 파일 로컬 다운로드 활성화 |

### 3) 메시지 및 보고서 파일 전송 (`send`)

```bash
# 1. 인라인 텍스트 전송 (나에게 보내기는 --chat "me")
tools/telegram-tools/src/telegram-tools.sh send --chat "me" --text "작업이 완료되었습니다."

# 2. 마크다운 보고서 파일 내용 전송 (4,000자 초과 시 자동 분할 발송)
tools/telegram-tools/src/telegram-tools.sh send --chat -1001234567 --file "report.md"

# 3. 사진 또는 파일 첨부 전송
tools/telegram-tools/src/telegram-tools.sh send --chat "회의방" --text "결과 파일 첨부합니다." --attach "result.zip"

# 4. 무음 알림 전송
tools/telegram-tools/src/telegram-tools.sh send --chat "회의방" --text "야간 배치 완료" --silent
```

### 4) 세션 연결 상태 점검 (`status`)
```bash
tools/telegram-tools/src/telegram-tools.sh status
```

---

## 📋 3. Output Formats (산출물 규격)

추출된 파일은 지정한 `--output-dir` (기본값: `tools/telegram-tools/src/exports/`)에 저장됩니다:

- **Markdown (`chat_<title>_<id>_<timestamp>.md`)**:
  - 상단 대화방 메타데이터(방 제목, ID, 추출 기간, 건수)
  - 타임라인형 발신자(`### 👤 발신자 · 일시`), 답글 인용문(`> quote`), 본문 텍스트, 첨부 미디어 태그
  - LLM 요약 프롬프트에 바로 삽입하기에 최적화됨.
- **JSON (`chat_<title>_<id>_<timestamp>.json`)**:
  - `chat`, `time_range`, `message_count`, `messages` 객체 구조
  - 메시지별 `id`, `date`, `sender`, `reply_to_msg_id`, `text`, `media` 보존.

---

## ⚠️ 4. Troubleshooting (문제 해결)

1. **"로그인이 필요합니다" / "세션 상태 미생성" 오류**:
   - 세션 파일이 없거나 만료된 상태입니다. 사용자에게 터미널에서 `cd tools/telegram-tools/src && ./telegram-tools.sh login`을 실행하도록 안내합니다.
2. **"대화방을 찾을 수 없습니다" 오류**:
   - `chats` 명령어로 정확한 방 이름이나 ID를 먼저 조회하여 `--chat` 인자로 전달합니다.
   - 비공개 그룹이나 채널의 경우 `-100...` 접두사가 포함된 정수 ID를 큰따옴표로 감싸서 전달합니다 (예: `--chat "-1001234567890"`).
3. **FloodWaitError (Rate Limit)**:
   - 텔레그램 서버 제한에 도달한 경우 스크립트가 지정된 초만큼 자동 대기 후 재시도합니다.
