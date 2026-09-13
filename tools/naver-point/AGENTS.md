# naver-point AI Agent 개발 및 유지보수 가이드 (SSOT)

이 문서는 `tools/naver-point` 도구를 개발, 유지보수, 리팩토링하는 AI 에이전트를 위한 서브프로젝트 전용 아키텍처 명세서이자 개발 지침서입니다.  
프로젝트 전역 규칙은 루트 [AGENTS.md](../../AGENTS.md)를 참조하십시오.

---

## 1. 서브프로젝트 개요 및 설계 철학

`naver-point`는 네이버페이 혜택 포인트 수집 및 캠페인 랜덤 뽑기를 완전 무인 또는 대화형 CLI로 수행하는 자동화 도구입니다.

### 1.1 핵심 설계 목표
- **완전 무인 실행(Headless) & 즉시 수동 로그인(Headful) 전환**:
  - 평소에는 헤드리스 모드로 고속 실행되며, 세션 만료 감지 시 자동으로 GUI 모드로 전환하거나 `login` 서브커맨드를 통해 즉시 재로그인 유도.
- **Google Drive & `gog` 기반 멀티 PC 세션 동기화**:
  - Chromium의 OS 키체인 종속적인 `user_data` 대신, OS 독립적인 Playwright 경량 세션 포맷(`naver_point_session.json`)을 Google Drive(`my-tools/naver-point/`)를 통해 동기화.
- **듀얼 출력 인터페이스 (Human vs Machine)**:
  - 인간이 터미널에서 실행할 때는 `rich` 콘솔의 스피너, 색상 로그, 테이블로 시각적 만족감을 제공.
  - 에이전트/Cron/스크립트 호출(`--json`) 시에는 `stdout`에 단 한 줄의 정형 JSON만 출력하여 파이프라인 연계 보장.

---

## 2. 아키텍처 및 모듈 구성 (`src/`)

```text
tools/naver-point/src/
├── naver-point.sh          # CLI 전역 심링크 래퍼 (uv run 호출)
├── main.py                 # Typer 기반 CLI 진입점 (run, balance, login, status, logout, sync)
├── core/
│   ├── config.py           # 상수, URL, 파일 경로 및 환경변수
│   ├── session.py          # NaverSessionManager (Playwright 컨텍스트 & 세션 생명주기)
│   ├── sync.py             # Google Drive / gog 세션 동기화 엔진
│   └── collector.py        # 혜택 클릭, 랜덤 카드 뽑기, 잔액 조회 엔진
└── tests/                  # 단위 및 통합 테스트
```

### 2.1 주요 모듈별 역할과 책임
1. **`core/config.py`**:
   - `NAVER_LOGIN_URL`: `https://nid.naver.com/nidlogin.login`
   - `NAVER_PAY_BENEFIT_URL`: `https://pay.naver.com/about/benefit`
   - `NAVER_CAMPAIGN_URL`: `https://m-campaign.naver.com/npay/gorandomp/?rcode=offpay`
   - `GOOGLE_DRIVE_FOLDER`: `my-tools/naver-point`
   - `SESSION_FILENAME`: `naver_point_session.json`
   - `ERROR_SCREENSHOT_PATH`: `logs/error_screenshot.png`
2. **`core/session.py` (`NaverSessionManager`)**:
   - `async with NaverSessionManager(...) as session:` 형태로 자원 관리.
   - 컨텍스트 생성 시 `--disable-blink-features=AutomationControlled` 인자를 필수로 주입하여 네이버 봇 탐지 우회.
   - `NID_SES` 쿠키 존재 여부 및 로그인 페이지 리다이렉트 여부로 로그인 상태 판별.
   - 세션 종료 시 `context.storage_state(path=...)`를 통해 세션 JSON을 갱신.
   - `clear_session()`: 로컬 및 클라우드 세션 파일을 삭제하고 초기화.
3. **`core/sync.py` (`SessionSyncManager`)**:
   - Google Drive Desktop 마운트 경로 탐색 (`~/Library/CloudStorage/GoogleDrive-.../내 드라이브/my-tools/naver-point/`).
   - 마운트 미발견 시 시스템의 `gog` CLI (`gog drive download` / `gog drive upload`)를 호출하여 클라우드 세션 동기화.
   - 둘 다 불가할 경우 로컬 OS 표준 경로(`~/.local/share/naver-point/`)로 폴백.
4. **`core/collector.py`**:
   - `fetch_point_balance(session)`: 현재 보유 네이버페이 포인트 잔액을 추출.
   - `harvest_benefits(session, dry_run=False)`: 혜택 페이지 버튼 탐색 및 순차 클릭 (dry-run 지원).
   - `harvest_random_draws(session, dry_run=False)`: 캠페인 페이지에서 '지금뽑기'/'한번 더' 카드를 탐색하여 클릭, 팝업 닫기, 새로고침 루프 수행.

---

## 3. DOM 셀렉터 및 스크레이핑 규칙 (Scraper Contracts)

네이버 웹 프론트엔드는 주기적으로 클래스명이 난독화되거나 UI 구조가 변경됩니다. 에이전트가 코드를 수정할 때는 다음 규칙을 엄수해야 합니다:

### 3.1 혜택 포인트 받기 셀렉터
단일 클래스명에만 의존하지 말고 텍스트 기반 및 복수 셀렉터 폴백 구조를 유지하십시오:
```python
SELECTORS = [
    "button:has-text('포인트 받기')",
    "a:has-text('포인트 받기')",
    "button:has-text('뽑기')",
    "a:has-text('뽑기')",
    ".BenefitItem_btn__click"
]
```
- 클릭 후 생성되는 새 탭이나 팝업은 `handle_extra_pages(context)`로 즉시 감지하여 닫아 브라우저 메모리 누수를 방지해야 합니다.

### 3.2 랜덤 카드 뽑기 셀렉터
- **대상 카드**: `.section_point_draw .draw_list a.card_draw` 중 텍스트가 `지금뽑기` 또는 `한번 더`를 포함하는 요소.
- **클릭 방식**: 단순 `click()` 실패 시 bounding box 기반 마우스 클릭 또는 JS evaluate `el.click()`으로 폴백.
- **팝업 닫기**: `button.btn_close, .close, :text('닫기')` 우선 탐색 후, 미노출 시 화면 상단 모서리(`(10, 10)`) 클릭 폴백.
- **상태 동기화**: 뽑기 1회 완료 후 반드시 `page.reload(wait_until="domcontentloaded")`를 수행하여 잔여 카드 상태를 재동기화해야 합니다.

### 3.3 포인트 잔액 추출 셀렉터
혜택 페이지 상단 및 네이버페이 헤더의 잔액 영역:
```python
BALANCE_SELECTORS = [
    ".my_point .num",
    ".point_num",
    "a[href*='point'] strong",
    "span:has-text('P')"
]
```
- 숫자 외의 문자(쉼표, '원', 'P' 등)를 제거하고 정수(`int`)로 파싱하여 반환합니다. 파싱 실패 시 `None`을 반환하며 전체 수집 흐름을 중단시켜서는 안 됩니다.

---

## 4. 에이전트 준수 가이드라인 (Crucial Guardrails for Agents)

1. **비밀값 및 세션 파일 커밋 절대 금지 (Never Commit Secrets)**:
   - `naver_point_session.json`, `cookies.json`, `user_data/` 등 세션 파일은 절대로 Git에 커밋하지 않습니다. `.gitignore`에 등록되어 있는지 항상 확인하십시오.
2. **랜덤 딜레이 유지 (Human-like Timing)**:
   - 모든 페이지 이동 및 클릭 사이에는 반드시 `await asyncio.sleep(random.uniform(1.0, 2.5))`와 같은 비결정론적 지연을 두어야 합니다. 고정된 sleep이나 딜레이 없는 연타는 계정 제재의 원인이 됩니다.
3. **자동 장애 진단 스크린샷 캡처 (Failure Diagnosis)**:
   - 수집 도중 예기치 못한 셀렉터 미발견이나 예외가 발생할 경우, 프로세스가 종료되기 직전에 `await page.screenshot(path="logs/error_screenshot.png")`을 호출하여 화면 상태를 자동 보존해야 합니다. 에이전트는 이 이미지를 통해 셀렉터 변경 여부를 즉각 진단할 수 있습니다.
4. **기계 판독용 JSON 출력 무결성 (JSON stdout Contract)**:
   - `--json` 플래그가 주어졌을 때, 표준 출력(`stdout`)에는 순수한 단일 라인 JSON 결과만 인쇄되어야 합니다:
   ```json
   {
     "status": "Success",
     "benefit_clicked": 3,
     "random_draws": 5,
     "starting_balance": 14200,
     "ending_balance": 14225,
     "earned_points": 25,
     "session_synced": true
   }
   ```
   - 모든 디버그 로그, 진행 상황 안내, 에러 트레이스는 `stderr`나 로깅 파일(`naver_point.log`)로만 출력해야 합니다.
5. **`uv` 패키지 관리 준수**:
   - 패키지 추가 시 임의의 `pip`를 사용하지 말고 반드시 `uv add <package>`를 사용하십시오.
   - 전역 CLI 래퍼인 `src/naver-point.sh`는 `uv run python -m main "$@"` 형태로 구동됩니다.
6. **순수 상대 경로 링크 준수**:
   - 본 문서나 관련 Markdown 내 모든 링크는 순수 상대 경로(`README.md`, `../../AGENTS.md`)를 사용하십시오.
