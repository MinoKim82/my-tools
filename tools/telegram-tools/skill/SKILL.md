---
name: telegram-tools
description: Read and inspect recent Telegram conversations, export chat history between specific time ranges into Markdown and JSON, send Telegram messages and file attachments, search and list active chat rooms, or check Telegram session status using the telegram CLI. ALWAYS trigger this skill whenever the user asks to read, check, summarize, export, or send anything via Telegram (e.g., "텔레그램 대화 읽어줘", "텔레그램 방금 무슨 얘기 나왔어?", "공지방 최근 대화 보여줘", "텔레그램 대화기록 백업해", "최근 24시간 텔레그램 대화 요약해줘", "이 회의록 텔레그램으로 전송해", "나한테 텔레그램 보내줘", "텔레그램 방에 메시지 보내", "텔레그램 채팅방 목록 보여줘", "텔레그램 세션 상태 확인해줘").
---

# Telegram Tools Skill

텔레그램(Telegram)의 실시간 대화 읽기(`read`/`show`), 기간별 대화 기록 추출 및 문서화(`export`), 메시지 및 파일 전송(`send`), 활성 대화방 검색(`chats`)을 수행하는 에이전트 전용 스킬입니다.

---

## 🚫 1. Agent Role & Guardrails (에이전트 권한 및 안전 규칙)

- **허용된 명령어 (자율 실행 가능)**:
  - `status`: 현재 텔레그램 계정 세션 상태 및 내 정보 확인
  - `chats`: 대화방 목록 조회 및 ID/Username 검색
  - `read` (또는 `show`, `history`): 대화방의 최근 대화 즉시 읽기 (터미널 뷰어)
  - `export`: 특정 대화방의 기간별 대화 기록 추출 및 문서화 (기본: Markdown `.md`, 옵션: `--json`, `--all`)
  - `send`: 메시지 텍스트, 마크다운 보고서 파일, 또는 첨부파일 전송
  - `logout`: 세션 파일 삭제
- **사용자 개입 필요 명령어 (`login`)**:
  - `login`은 텔레그램 앱으로 전송되는 인증 코드와 2FA 비밀번호 입력을 요구하므로 에이전트가 직접 실행하지 않고 사용자에게 직접 터미널 실행(`telegram login`)을 안내합니다.
- **실행 진입점**:
  - 전역 CLI 등록 시: `telegram <command>` (또는 `telegram-tools <command>`)
  - 로컬 스크립트 직접 호출 시: `tools/telegram-tools/src/telegram-tools.sh <command>`

---

## 🧭 2. Intent to Command Mapping (사용자 의도별 명령어 매핑)

| 사용자 요청 패턴 | 실행 명령어 |
|---|---|
| "텔레그램 대화 읽어줘 / 최근 대화 보여줘" | `telegram read "<방이름>" --limit 20` |
| "최근 2시간 동안 무슨 얘기 오갔어?" | `telegram read "<방이름>" --since "2h"` |
| "텔레그램 대화 가져와서 요약해줘" | `telegram export "<방이름>" --since "24h"` 실행 후 생성된 `.md` 파일 읽어서 요약 |
| "나한테 텔레그램 메시지 보내줘" | `telegram send "me" --text "내용..."` |
| "이 마크다운 파일 텔레그램 방에 보내줘" | `telegram send "<방이름>" --file "<파일경로>"` |
| "텔레그램 방 목록 / 방 ID 확인해줘" | `telegram chats --search "<키워드>"` |
| "텔레그램 로그인 잘 되어있어?" | `telegram status` |

---

## 🔄 3. Multi-Step Agent Workflows (핵심 시나리오별 실행 레시피)

### Recipe 1: 대화 확인 및 요약 요청 처리 ("이 방 최근 대화 요약해줘")
1. **대화방 확인**: 사용자가 지정한 방 이름이 모호하면 `telegram chats --search "<방이름>"`으로 확인합니다.
2. **대화 수집**:
   - 짧은 확인: `telegram read "<방이름>" --limit 30` 실행 후 출력 텍스트 분석.
   - 기간 기준 요약: `telegram export "<방이름>" --since "24h"` (또는 `--since "yesterday"`) 실행.
3. **문서 확인 및 요약**:
   - `export` 시 출력된 마크다운 경로(예: `exports/chat_...md`)를 읽고 주요 논의 사항, 결정 사항, 액션 아이템을 정리하여 사용자에게 보고합니다.

### Recipe 2: 작업 결과물 및 보고서 발송 ("이 분석 결과 텔레그램으로 전송해")
1. **파일 전송**:
   - `telegram send "<방이름>" --file "<결과보고서.md>"`
   - 4,000자 초과 시 CLI가 단락/문장 단위로 자동 분할 전송하므로 파일 크기 걱정 없이 전송 가능합니다.
2. **개인 알림(나에게 보내기)**:
   - `--chat "me"`를 사용하면 본인의 "저장한 메시지(Saved Messages)"로 안전하게 전송됩니다:
     `telegram send "me" --text "✅ 작업이 성공적으로 완료되었습니다."`

---

## 📖 4. Command Reference & Options (상세 명령어 규격)

### 1) 대화방 목록 조회 및 검색 (`chats`)
```bash
telegram chats                    # 최근 대화방 20개 출력
telegram chats --search "회의"     # 대화방 제목 검색
telegram chats --limit 50         # 최대 50개 조회
```

### 2) 대화 즉시 읽기 (`read` / `show` / `history`)
파일을 디스크에 저장하지 않고 터미널에서 대화 내용을 빠르게 확인합니다:
```bash
telegram read "팀 프로젝트"                 # 최근 20개 대화 출력 (위치 인자)
telegram read "팀 프로젝트" --limit 50      # 최근 50개 대화 출력
telegram read "@proj_room" --since "2h"     # 최근 2시간 대화만 출력
telegram show "공지방" --pager             # 터미널 페이저(스크롤)로 보기
```

### 3) 대화 기록 추출 및 문서화 (`export`)
지정 기간의 대화를 정형 문서 파일로 내보냅니다:
```bash
# 기본: Markdown(.md) 파일만 1개 저장
telegram export "팀 프로젝트" --since "24h"

# JSON(.json) 파일만 저장
telegram export "팀 프로젝트" --since "yesterday" --json

# Markdown과 JSON 파일 둘 다 동시 저장
telegram export "팀 프로젝트" --since "3d" --all

# 특정 날짜 범위 지정 및 미디어(사진/문서) 다운로드
telegram export -1001234567 --since "2026-09-20 00:00" --until "2026-09-22 23:59" --download-media --output-dir "./logs"
```

| 옵션 | 단축키 | 기본값 | 설명 |
|---|---|---|---|
| `[chat]` | | *(필수)* | 위치 인자로 대화방 이름, ID(정수), 또는 `@username` 전달 |
| `--since` | `-s` | `"24h"` | 시작 시각 (`2h`, `24h`, `3d`, `yesterday`, `YYYY-MM-DD HH:MM`) |
| `--until` | `-u` | `"now"` | 종료 시각 (`now`, `YYYY-MM-DD HH:MM`) |
| `--md` | | `True` | 마크다운(`.md`) 파일 저장 (기본값) |
| `--json` | | `False` | JSON(`.json`) 파일 저장 |
| `--all` | | `False` | 마크다운과 JSON 모두 저장 |
| `--output-dir` | `-o` | `"exports"` | 문서 저장 디렉토리 |
| `--download-media` | | `False` | 사진/문서/음성 파일 로컬 다운로드 활성화 |
| `--limit` | `-l` | `1000` | 가져올 최대 메시지 수 제한 |

### 4) 메시지 및 파일 발송 (`send`)
```bash
telegram send "me" --text "메모 전송"                     # 나에게 전송
telegram send "회의방" --file "summary.md"                # 긴 문서 파일 내용 전송 (4000자 자동 분할)
telegram send "회의방" --text "보고서" --attach "file.pdf" # 첨부파일과 함께 전송
telegram send "회의방" --text "무음 알림" --silent         # 무음 알림 전송
```

### 5) 세션 상태 점검 (`status`)
```bash
telegram status
```

---

## ⚠️ 5. Troubleshooting (문제 해결 가이드)

1. **"로그인이 필요합니다" / 세션 미연결**:
   - 세션이 없거나 만료된 상태입니다. 에이전트가 직접 `login`을 돌리지 말고, 사용자에게 터미널에서 `telegram login`을 1회 실행하도록 안내합니다.
2. **"대화방을 찾을 수 없습니다"**:
   - 대화방 이름의 띄어쓰기나 오타를 점검하고, `telegram chats --search "<키워드>"`로 검색된 정확한 이름이나 Chat ID를 사용합니다.
   - 슈퍼그룹/채널 음수 ID(예: `-1001234567`)는 셸 옵션 오인 방지를 위해 반드시 큰따옴표로 감싸서 전달합니다 (`telegram export "-1001234567"`).
3. **Rate Limit (`FloodWaitError`)**:
   - 스크립트 내부에서 텔레그램 서버 제한 시간을 자동 감지하여 대기 후 재시도하므로 강제 종료하지 않고 대기합니다.
