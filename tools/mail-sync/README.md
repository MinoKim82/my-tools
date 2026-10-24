# mail-sync

Gmail을 통해 정기 수신되는 카드사(우리, 현대, 삼성) 명세서와 은행(우리은행) 대출 통지 메일을 감지하여, 보안 HTML 첨부파일 복호화, Google Drive 원본 백업, 정규화된 CSV 원장 저장 및 옵시디언(Obsidian) 가족 금융 대시보드로 자동 정리하는 **2단 확장형 메일 자동화 CLI 도구**입니다.

> 태그: `[CLI]` `[FINANCE]` `[OBSIDIAN]` `[GMAIL]` `[SCRIPT]`

---

## 📌 주요 특징 및 기능

1. **2단 파이프라인 아키텍처 (Filter & Dispatcher)**:
   * **1단계 코어 엔진**: Gmail 쿼리 검색, 중복 처리 방지(`data/state.json`), 플러그인 자동 탐색.
   * **2단계 도메인 서브모듈 (`handlers/`)**: `finance` 핸들러가 탑재되어 있으며, 추후 세금(tax), 증권(stock) 등 파일 1개만 추가하여 쉽게 확장 가능.
2. **동적 기간 필터링 (Fast Incremental Sync)**:
   * 기본적으로 **최근 1일(`newer_than:1d`)** 동안 수신된 메일만 검색하므로 평상시 1~2초 만에 스캔 후 초경량으로 종료 (서버 crontab 최적화).
   * 옵션을 통해 `--days 7`, `--month 2026-10`, `--all` 기간 선택 가능.
3. **카드 3사 보안 HTML 자동 복호화**:
   * 생년월일 6자리(`BIRTH_DATE_6DIGIT`) 기반으로 Playwright 헤드리스 브라우저를 통해 VestMail, Initech 등 보안 명세서 자동 복호화 및 청구금액 추출.
4. **옵시디언 볼트(`areas/family/finance/`) 완벽 연동**:
   * **📄 `가족 금융 대시보드.md`**: 옵시디언에서 바로 보는 월간 결제 캘린더 (12일 현대 ➔ 13일 삼성 ➔ 14일 우리 ➔ 15일 우리은행 대출) 및 핵심 KPI 브리핑.
   * **📊 `가족_금융_원장.csv`**: 외부 모바일 앱, 가계부 스크립트, 대시보드 API와 연동 가능한 단일 정규화 Flat 원장.
   * **📁 `statements/YYYY-MM/`**: 복호화된 원본 명세서 HTML 백업.
   * **🔗 `가족 공통 홈.md`**: 대시보드 링크 자동 상호 연결.
5. **외부 애플리케이션 연동 (`mail-sync export`)**:
   * `mail-sync export --json` 명령어로 로컬 앱 및 위젯에서 언제든 최신 금융 데이터를 JSON으로 수신.

---

## 🛠️ 준비 사항 및 환경 설정

### 1. 필수 요구조건
* **Python**: 3.11 이상
* **패키지 매니저**: `uv` (`brew install uv`)
* **Google CLI**: `gog` CLI (`brew install gogcli`, 계정 인증 완료 상태)

### 2. 환경변수 설정
`tools/mail-sync/src/.env` 파일을 생성하고 카드 복호화 비밀번호를 입력합니다:
```bash
# .env.example 복사
cp tools/mail-sync/src/.env.example tools/mail-sync/src/.env

# .env 파일 편집
BIRTH_DATE_6DIGIT=820101           # 사용자 생년월일 6자리 (YYMMDD)
GOOGLE_ACCOUNT=minokim82@gmail.com
```

---

## 🚀 CLI 사용법

```bash
# 1. 기본 동기화 실행 (최근 1일 수신 메일 스캔 - crontab용)
mail-sync run

# 2. 특정 기간 지정 동기화
mail-sync run --days 7             # 최근 7일치 스캔
mail-sync run --month 2026-10      # 2026년 10월 전체 스캔
mail-sync run --all               # 과거 전체 데이터 백필

# 3. 이번 달 12~15일 결제 일정 및 통장별 필요 잔고 터미널 출력
mail-sync finance calendar

# 4. 외부 앱 연동용 정규화 JSON 데이터 출력
mail-sync export --json
mail-sync export --month 2026-10 --json

# 5. 등록된 핸들러 및 최근 동기화 통계 상태 확인
mail-sync status
```

---

## ⏰ 서버 Crontab 등록 가이드

24시간 가동되는 Linux 서버 또는 로컬 Mac에서 매일 아침 정기 실행하도록 등록합니다:

```bash
crontab -e
```

```cron
# 매일 아침 09:00에 1일치 신규 금융 메일 점검 및 옵시디언 동기화
0 9 * * * /Users/kimminho/.local/bin/mail-sync run >> /Users/kimminho/.local/state/mail-sync.log 2>&1
```

---

## 📂 파일 생성 위치 및 구조

Google Drive 상의 Obsidian Vault `areas/family/finance/` 아래에 다음과 같이 생성 및 유지됩니다:
```text
areas/family/
├── 가족 공통 홈.md                   # [[가족 금융 대시보드]] 링크 자동 연결
├── 가족 보험 대시보드.md
├── subscription/
└── finance/
    ├── 가족 금융 대시보드.md          # 최신 결제 캘린더 & KPI 요약 브리핑
    ├── 가족_금융_원장.csv            # 외부 앱/API 연동용 Flat 데이터베이스
    └── statements/
        └── 2026-10/
            ├── 현대카드_2026-10.html
            ├── 삼성카드_2026-10.html
            └── 우리카드_2026-10.html
```
