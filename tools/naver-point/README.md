# naver-point

네이버페이(Naver Pay) 혜택 포인트 자동 수집 및 캠페인 랜덤 카드 뽑기를 수행하는 전용 자동화 CLI 유틸리티입니다.

> 태그: `[CLI]` `[SCRIPT]`

---

## 📌 주요 특징 및 기능

1. **직관적인 CLI 인터페이스 (`typer` + `rich`)**:
   - `naver-point run`: 포인트 수집 전체 실행 (혜택 클릭 + 랜덤 카드 뽑기)
   - `naver-point run --benefit-only`: 혜택 페이지 버튼만 수집
   - `naver-point run --draw-only`: 캠페인 랜덤 카드만 뽑기
   - `naver-point login`: GUI 브라우저 창을 띄워 네이버 로그인 수행 및 세션 추출
   - `naver-point status`: 현재 세션의 만료 여부 및 로그인 상태 점검
   - `naver-point sync [push|pull]`: Google Drive와 세션 파일 수동 동기화

2. **다중 PC 세션 동기화 (Google Drive & `gog` 브릿지)**:
   - 세션 데이터를 기기 독립적인 경량 JSON 포맷(`naver_point_session.json`, 약 10KB)으로 관리합니다.
   - **Google Drive 경로**: Google Drive 상의 `my-tools/naver-point/naver_point_session.json`
   - **동기화 우선순위 (Smart Sync Fallback)**:
     1. 환경변수 `NAVER_POINT_SESSION_PATH` 지정 경로
     2. Google Drive Desktop 로컬 마운트 경로 (`~/Library/CloudStorage/GoogleDrive-.../내 드라이브/my-tools/naver-point/`)
     3. 시스템에 설치된 `gog` CLI (`gog drive download` / `gog drive upload`)
     4. OS 표준 로컬 경로 (`~/.local/share/naver-point/naver_point_session.json`)

3. **듀얼 출력 인터페이스 (Human TTY vs Machine JSON)**:
   - **터미널 실행 (인간)**: 진행 스피너, 컬러 상태 로그, 수집 결과 요약 테이블 출력.
   - **자동화/스크립트/에이전트 실행 (`--json`)**: 파이프라인 처리가 용이한 단일 라인 JSON 출력.

4. **안티 봇 디텍션 및 안정적 세션 복원**:
   - Playwright의 `--disable-blink-features=AutomationControlled` 플래그 및 인간적인 랜덤 딜레이(1.0~3.0초) 적용.
   - 세션 쿠키와 localStorage를 한 번에 주입/복원하여 2차 인증 피로도 최소화.

---

## 🛠️ 준비 사항 및 설치

### 1. 필수 요구조건
- **Python**: 3.11 이상
- **패키지 매니저**: `uv` (필수 권장)
- **(선택) Google Drive 동기화**: Google Drive for Desktop 앱 또는 `gog` CLI (`brew install gogcli`)

### 2. 도구 환경 설치
```bash
# 1. 도구 src 디렉토리로 이동
cd tools/naver-point/src

# 2. 의존성 설치 및 가상환경 생성
uv sync

# 3. Playwright Chromium 브라우저 설치
uv run playwright install chromium
```

---

## 🚀 전역 등록 및 빠른 실행 (Quick Start)

저장소 루트 디렉토리에서 `Makefile`을 통해 전역 CLI 및 에이전트 스킬로 등록할 수 있습니다.

```bash
# 저장소 루트(my-tools/)에서 실행
make link tool=naver-point         # ~/.local/bin/naver-point 등록
make link-skill tool=naver-point   # ~/.gemini/config/skills/naver-point 등록
```

### 최초 로그인
최초 실행 시 브라우저 창에서 1회 로그인을 완료해야 합니다.
```bash
naver-point login
```
로그인이 완료되면 세션 쿠키가 `naver_point_session.json`으로 저장되고, Google Drive로 자동 업로드/동기화됩니다.

---

## 📖 CLI 명령어 가이드

### 1. 포인트 수집 (`run`)
```bash
# 전체 수집 (혜택 포인트 클릭 + 캠페인 랜덤 뽑기)
naver-point run

# 헤드리스 모드 (백그라운드 무인 실행)
naver-point run --headless

# 혜택 페이지만 수집
naver-point run --benefit-only

# 랜덤 뽑기 페이지만 수집
naver-point run --draw-only

# 기계 판독용 JSON 출력 (스크립트/Cron 연동용)
naver-point run --json
```

### 2. 세션 점검 (`status`)
```bash
naver-point status
```
- 세션 파일 존재 여부, 만료 여부, 네이버 로그인 상태를 헤드리스로 빠르게 점검합니다.

### 3. 클라우드 세션 수동 동기화 (`sync`)
```bash
# 로컬 세션을 Google Drive(my-tools/naver-point/)로 업로드
naver-point sync push

# Google Drive에서 최신 세션을 다운로드
naver-point sync pull
```

---

## 📂 파일 구조

```text
tools/naver-point/
├── README.md               # 사용자 및 CLI 가이드 (본 문서)
├── AGENTS.md               # 도구 전용 유지보수/DOM 셀렉터 SSOT (에이전트용)
├── skill/
│   └── SKILL.md            # AI 에이전트 런타임 스킬 명세 (/skill-creator 규격)
└── src/
    ├── pyproject.toml      # Python 의존성 (playwright, typer, rich 등)
    ├── .env.example        # 환경 변수 템플릿
    ├── naver-point.sh      # CLI 전역 실행 래퍼 스크립트
    ├── main.py             # CLI 진입점 (Typer 앱)
    ├── core/               # 브라우저 세션 및 수집 엔진
    │   ├── session.py      # Playwright 세션 및 스토리지 관리자
    │   ├── sync.py         # Google Drive / gog 세션 동기화 모듈
    │   ├── collector.py    # 혜택 포인트 및 랜덤 카드 뽑기 로직
    │   └── config.py       # URL 및 기본 경로 설정
    └── tests/              # 단위 테스트 및 검증 스크립트
```
